"""End-to-end public literature tracker. Network calls happen in GitHub Actions."""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, date, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from tracker.core import merge_catalog, now_iso
from tracker.http import client, audit
from tracker.site import build
from tracker.sources import pubmed, arxiv, medrxiv, crossref

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


def read_json(path: Path, fallback):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return fallback


def truncate_for_publication(paper: dict) -> dict:
    """Avoid republishing entire third-party copyrighted abstracts in a public repo."""
    public = dict(paper)
    excerpt = paper.get("abstract", "")
    public["abstract"] = excerpt[:240] + ("…" if len(excerpt) > 240 else "")
    return public


def scan_all(session, start: date, end: date, catalog: dict, max_items: int):
    audits: list[dict] = []
    all_new: list[str] = []
    updates = 0
    methods = [
        ("pubmed", lambda: pubmed.scan(session, start, end, max_items)),
        ("arxiv", lambda: arxiv.scan(session, start, end, max_items)),
        ("medrxiv", lambda: medrxiv.scan(session, start, end, max_items)),
        ("crossref-journal", lambda: crossref.scan(session, start, end, max(200, max_items // 8))),
    ]
    for name, func in methods:
        try:
            papers, rows = func()
        except Exception as exc:
            papers = []
            rows = [audit(name, "fatal", "unhandled source error", "unknown", f"{start}/{end}", error=str(exc)[:350])]
        before = len(catalog)
        new_keys, updates_this_source = merge_catalog(catalog, papers)
        all_new.extend(new_keys)
        updates += updates_this_source
        audits.extend(rows)
        print(f"[{name}] retrieved unique source papers={len(papers)}; added={len(catalog) - before}; complete query rows={sum(int(x['complete']) for x in rows)}/{len(rows)}", flush=True)
    # Refresh existing medRxiv DOIs for 30-day version changes. This check is bounded and audited.
    try:
        versioned, version_rows = medrxiv.check_versions(session, catalog, end)
        version_new, version_updates = merge_catalog(catalog, versioned)
        all_new.extend(version_new)
        updates += version_updates
        audits.extend(version_rows)
    except Exception as exc:
        audits.append(audit("medrxiv", "version_refresh", "known 30d versions", "version", f"{start}/{end}", error=str(exc)[:350]))
    return audits, sorted(set(all_new)), updates


def run(days: int = 7, max_items: int = 3000, dry_run: bool = False) -> dict:
    DATA.mkdir(parents=True, exist_ok=True)
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=days)
    date_la = datetime.now(ZoneInfo("America/Los_Angeles")).date().isoformat()
    catalog: dict[str, dict] = read_json(DATA / "catalog.json", {})
    history: list[dict] = read_json(DATA / "history.json", [])
    audits, new_keys, updates = scan_all(client(), start, end, catalog, max_items)
    # Only preserve a short metadata/excerpt excerpt in the public repository.
    for key in catalog:
        catalog[key] = truncate_for_publication(catalog[key])
    new_papers = [catalog[key] for key in new_keys if key in catalog]
    new_papers.sort(key=lambda p: (p.get("score", 0), p.get("published", "")), reverse=True)
    completed = sum(int(r["complete"]) for r in audits)
    summary = {
        "schema_version": 1,
        "date_la": date_la,
        "run_at_utc": now_iso(),
        "window_start_utc_date": start.isoformat(),
        "window_end_utc_date": end.isoformat(),
        "note": "Rolling UTC date window; not exact 24-hour publication time. Source indexing delays possible. Scores are heuristic, not evidence appraisal.",
        "queries_completed": completed,
        "queries_attempted": len(audits),
        "complete": bool(audits) and all(r["complete"] for r in audits),
        "catalog_size": len(catalog),
        "new_count": len(new_papers),
        "updated_count": updates,
        "audits": audits,
        "new_papers": new_papers[:250],
        "omitted_new_paper_count": max(0, len(new_papers)-250),
    }
    history = ([{"date_la": date_la, "run_at_utc": summary["run_at_utc"], "complete": summary["complete"], "new_count": summary["new_count"], "queries_completed": completed, "queries_attempted": len(audits)}] + history)[:120]
    # By default, site is rebuilt even if upstream searches fail. A partial report is
    # more useful than silently leaving yesterday's report looking fresh.
    if not dry_run:
        (DATA / "catalog.json").write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")
        (DATA / "history.json").write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
        (DATA / "latest.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        build(summary, ROOT / "_site", history)
    return summary


def main():
    parser = argparse.ArgumentParser(description="Medical/Ophthalmic AI literature survey (auditable, no fabricated counts)")
    parser.add_argument("--days", type=int, default=int(os.getenv("LOOKBACK_DAYS", "7")), help="UTC rolling backfill days, 1..30")
    parser.add_argument("--max-items", type=int, default=3000, help="Per-query cap. If reached, audit is incomplete.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if not (1 <= args.days <= 30) or not (100 <= args.max_items <= 20000):
        parser.error("--days 1..30, --max-items 100..20000")
    result = run(args.days, args.max_items, args.dry_run)
    print(json.dumps({k: result[k] for k in ("date_la", "new_count", "catalog_size", "queries_completed", "queries_attempted", "complete")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
