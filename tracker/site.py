"""Build a self-contained, accessible, public static GitHub Pages dashboard."""
from __future__ import annotations

import html
import json
import shutil
from pathlib import Path
from urllib.parse import urlparse

CSS = """
:root{color-scheme:light;font:16px/1.6 system-ui,-apple-system,'Noto Sans SC',sans-serif;color:#203147;background:#f5f7fb}
*{box-sizing:border-box}main{max-width:1120px;margin:auto;padding:28px 18px 70px}
header{padding:35px 30px;background:linear-gradient(110deg,#142944,#254c68);color:#fff;border-radius:19px}
h1{font-size:clamp(1.8rem,4vw,2.7rem);margin:.2em 0}h2{margin:36px 0 10px;font-size:1.35rem}
header p{margin:5px 0;color:#d9e5f1}.eyebrow{color:#91d7ed;text-transform:uppercase;letter-spacing:.15em;font-size:.75rem;font-weight:bold}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin:20px 0}.card,.paper,.notice{background:white;border:1px solid #e1e8f0;box-shadow:0 2px 5px #132e4b0a;border-radius:13px;padding:17px}
.card strong{font-size:1.9rem;display:block}.card span{color:#627386;font-size:.86rem}
.notice{border-left:4px solid #d18d31;padding:15px 18px}.ok{border-left-color:#34876e}
.papers{display:grid;gap:15px}.paper h3{font-size:1.08rem;margin:.3em 0}.paper a{color:#146a99;text-decoration:none}.paper a:hover{text-decoration:underline}.paper p{color:#435367;margin:.45em 0}.meta{color:#667991;font-size:.82rem;display:flex;gap:9px;flex-wrap:wrap}.pill{border-radius:999px;padding:2px 9px;background:#eaf0f7;color:#34536f}
input,select{padding:11px 12px;border:1px solid #b9c8d8;border-radius:10px;font:inherit;background:#fff;min-width:0}#q{flex:1;min-width:180px}.filters{display:flex;flex-wrap:wrap;gap:10px;margin:18px 0}
table{width:100%;border-collapse:collapse;background:white;border-radius:11px;overflow:hidden;font-size:.86rem}td,th{padding:10px 12px;border-bottom:1px solid #e4ebf3;text-align:left;vertical-align:top}th{background:#e8eef5}td.error{color:#b94c37}.scroll{overflow-x:auto}
footer{margin-top:32px;color:#718095;font-size:.83rem}a{overflow-wrap:anywhere}button{cursor:pointer}
"""

def esc(t: object) -> str:
    return html.escape(str(t or ""), quote=True)


def safe_link(s: str) -> str:
    return s if urlparse(s).scheme in ("http", "https") else "#"


def build(result: dict, output_dir: Path, history: list[dict] | None = None) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "data").mkdir(exist_ok=True)
    (output_dir / "data" / "latest.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    (output_dir / "data" / "history.json").write_text(json.dumps(history or [], indent=2, ensure_ascii=False), encoding="utf-8")
    (output_dir / ".nojekyll").write_text("", encoding="utf-8")
    audit = result.get("audits", [])
    complete = sum(bool(a.get("complete")) for a in audit)
    total = len(audit)
    incomplete = total - complete
    papers = result.get("new_papers", [])
    la_date = esc(result.get("date_la", ""))
    states = "完整" if not incomplete and total else "部分检索"
    audit_html = "".join(f'<tr><td>{esc(a.get("source"))}</td><td>{esc(a.get("query_id"))}</td><td>{esc(a.get("date_field"))}</td><td>{esc(a.get("total") if a.get("total") is not None else "未知")}</td><td>{esc(a.get("fetched"))}</td><td>{"完成" if a.get("complete") else "未完成"}</td><td class="error">{esc(a.get("error") or a.get("next_cursor") or "")}</td></tr>' for a in audit)
    paper_html = ""
    for p in papers:
        domain = esc(p.get("domain"))
        status = "预印本｜未经同行评审" if p.get("review_status") == "preprint" else ("已发表｜期刊索引" if p.get("review_status") == "peer_reviewed" else "审核状态未知")
        url = esc(safe_link(p.get("url", "")))
        authors = "; ".join(p.get("authors", [])[:8])
        abstract = p.get("abstract", "")
        abstract_text = abstract[:550] + ("…" if len(abstract) > 550 else "")
        paper_html += f'<article class="paper" data-search="{esc((p.get("title", "") + " " + domain + " " + abstract).lower())}" data-domain="{domain}"><div class="meta"><span class="pill">{domain}</span><span>{esc(status)}</span><span>{esc(p.get("published") or "日期待核")}</span><span>{esc(p.get("source"))}</span></div><h3><a href="{url}" target="_blank" rel="noopener noreferrer">{esc(p.get("title"))}</a></h3><p>{esc(authors)}</p><p>{esc(abstract_text) or "来源未提供摘要；待核验"}</p><div class="meta">ID: {esc(p.get("doi") or p.get("source_id"))} · 优先级（规则筛选）：{esc(p.get("score"))}/3 · 待核查方法与实验数值</div></article>'
    if not paper_html:
        paper_html = '<div class="notice">本轮没有已筛选出的新增论文。不能据此断言这段时间没有相关论文。</div>'
    latest_link = "./data/latest.json"
    page = f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="Medical AI and Ophthalmic AI literature monitoring, with auditable coverage"><title>每日医学 AI · 眼科 AI 文献</title><style>{CSS}</style></head><body><main><header><div class="eyebrow">Research literature radar</div><h1>每日医学 AI × 眼科 AI 文献</h1><p>{la_date} · 最近一次 GitHub Actions 执行: {esc(result.get("run_at_utc"))} UTC</p><p>PubMed / arXiv / medRxiv / Crossref 期刊索引 · 检索证据与失败透明公开</p></header><div class="cards"><div class="card"><strong>{len(papers)}</strong><span>本次新增相关论文</span></div><div class="card"><strong>{complete}/{total}</strong><span>完成的查询/实际查询</span></div><div class="card"><strong>{incomplete}</strong><span>未完成或失败查询</span></div><div class="card"><strong>{esc(result.get("catalog_size", 0))}</strong><span>去重文献累计量</span></div></div><div class="notice {'ok' if states == '完整' else ''}"><strong>{states}</strong>：查询完成率不是文献召回率；Crossref 为期刊索引，不能证明逐刊官方 online-first 全覆盖。摘要与数字需复核原文，预印本未经同行评审。</div><h2>本次新增论文</h2><div class="filters"><input id="q" aria-label="检索论文" placeholder="搜索标题、摘要、疾病或方法…"><select id="domain" aria-label="研究方向"><option value="">全部方向</option><option value="Medical AI">Medical AI</option><option value="Medical Agent">Medical Agent</option><option value="Ophthalmic AI">Ophthalmic AI</option><option value="Ophthalmic Agent">Ophthalmic Agent</option></select></div><section class="papers" id="papers">{paper_html}</section><h2>来源级检索审计</h2><p>每一行表示实际尝试的来源与查询。全部数据可通过 <a href="{latest_link}">latest.json</a> 下载，用于 ChatGPT 每日报告。</p><div class="scroll"><table><thead><tr><th>来源</th><th>查询</th><th>日期字段</th><th>平台命中</th><th>已取回</th><th>状态</th><th>断点 / 错误</th></tr></thead><tbody>{audit_html}</tbody></table></div><footer>静态公开页面。无用户病历、Notion 令牌或 GitHub 密钥。自动规则评分不等于人工临床证据评估。<a href="./data/history.json">历史运行记录</a></footer></main><script>const q=document.querySelector('#q'),d=document.querySelector('#domain');function filter(){{let s=q.value.trim().toLowerCase(),v=d.value;for(const p of document.querySelectorAll('.paper'))p.hidden=!(p.dataset.search.includes(s)&&(!v||p.dataset.domain===v))}}q.addEventListener('input',filter);d.addEventListener('change',filter);</script></body></html>'''
    (output_dir / "index.html").write_text(page, encoding="utf-8")
