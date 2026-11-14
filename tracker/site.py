"""Build the English publication calendar and public literature archive."""
from __future__ import annotations

import html
import json
import shutil
from pathlib import Path
from urllib.parse import urlparse


def esc(value: object) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def safe_link(value: str) -> str:
    return value if urlparse(value).scheme in ("http", "https") else "#"


def build(result: dict, output_dir: Path, catalog: dict, history: list[dict] | None = None) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "data").mkdir(exist_ok=True)
    for filename, data in (("latest.json", result), ("history.json", history or []), ("catalog.json", catalog)):
        (output_dir / "data" / filename).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    (output_dir / ".nojekyll").write_text("", encoding="utf-8")
    (output_dir / "assets").mkdir(exist_ok=True)
    for filename in ("site.css", "calendar.js"):
        shutil.copyfile(Path(__file__).with_name("static") / filename, output_dir / "assets" / filename)

    audits = result["audits"]
    complete = sum(bool(row["complete"]) for row in audits)
    total = len(audits)
    state = "Retrieval complete" if total and complete == total else "Partial retrieval"
    index_names = {
        "pubmed": "Journal literature index",
        "arxiv": "arXiv",
        "medrxiv": "medRxiv",
        "crossref-journal": "Journal DOI index",
    }
    audit_rows = "".join(
        f'<tr><td>{index_names[row["source"]]}</td><td>{esc(row["query_id"])}</td>'
        f'<td>{esc(row["date_field"])}</td><td>{esc(row.get("total") if row.get("total") is not None else "Unknown")}</td>'
        f'<td>{esc(row["fetched"])}</td><td>{"Complete" if row["complete"] else "Incomplete"}</td>'
        f'<td class="error">{esc(row.get("error") or row.get("next_cursor") or "")}</td></tr>'
        for row in audits
    )
    papers = sorted(catalog.values(), key=lambda paper: (paper["published"], paper["score"]), reverse=True)
    articles = []
    for position, paper in enumerate(papers):
        venue = paper["venue"]
        if paper["source"] == "medrxiv" and paper["review_status"] == "preprint":
            venue = "medRxiv"
        is_preprint = paper["review_status"] == "preprint" or venue.lower().startswith(("arxiv", "medrxiv", "biorxiv"))
        status = "Preprint" if is_preprint else "Journal article" if paper["review_status"] == "peer_reviewed" else "Review status unknown"
        search = " ".join((paper["title"], paper["abstract"], venue, paper["domain"])).lower()
        published = paper["published"]
        date_label = f'<time datetime="{esc(published)}">{esc(published)}</time>' if published else "Publication date unavailable"
        articles.append(f'''<article class="paper" data-search="{esc(search)}" data-domain="{esc(paper['domain'])}" data-published="{esc(published)}"{' hidden' if position >= 50 else ''}>
  <div class="meta"><span class="pill">{esc(paper['domain'])}</span><span>{esc(status)}</span><span>{date_label}</span></div>
  <div class="venue">{esc(venue or 'Journal not specified')}</div>
  <h3><a href="{esc(safe_link(paper['url']))}" target="_blank" rel="noopener noreferrer">{esc(paper['title'])}</a></h3>
  <p class="authors">{esc('; '.join(paper['authors'][:8]))}</p>
  <p>{esc(paper['abstract']) or 'No abstract excerpt available.'}</p>
  <div class="meta">ID: {esc(paper['doi'] or paper['source_id'])} · Screening priority: {esc(paper['score'])}/3</div>
</article>''')
    page = f'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta name="description" content="Browse medical and ophthalmic AI journal articles and preprints by publication date.">
  <title>Medical &amp; Ophthalmic AI Literature</title>
  <link rel="stylesheet" href="./assets/site.css">
  <script src="./assets/calendar.js" defer></script>
</head>
<body data-calendar-date="{esc(result['window_end_utc_date'])}">
<main>
  <header>
    <div class="eyebrow">Research literature radar</div>
    <h1>Medical &amp; Ophthalmic AI</h1>
    <p>Explore journal articles and preprints by publication date.</p>
    <p class="updated">Last updated: {esc(result.get('run_at_utc', 'Not yet run'))} · UTC</p>
  </header>
  <div class="cards">
    <div class="card"><strong>{len(papers):,}</strong><span>Papers in the archive</span></div>
    <div class="card"><strong>{esc(result.get('new_count', 0))}</strong><span>Added in the latest scan</span></div>
    <div class="card"><strong>{complete}/{total}</strong><span>Queries completed</span></div>
  </div>
  <div class="browse-layout">
    <aside class="calendar-panel" aria-labelledby="calendar-title">
      <h2 id="calendar-title">Publication calendar</h2>
      <p class="muted">Select a day to find papers published on that date. Counts reflect your search filters.</p>
      <div class="calendar-nav">
        <button type="button" id="previous-month" aria-label="Previous month">&#8592;</button>
        <h3 id="calendar-month"></h3>
        <button type="button" id="next-month" aria-label="Next month">&#8594;</button>
      </div>
      <div class="weekdays" aria-hidden="true"><span>Sun</span><span>Mon</span><span>Tue</span><span>Wed</span><span>Thu</span><span>Fri</span><span>Sat</span></div>
      <div id="calendar-days" class="calendar-days" role="group" aria-labelledby="calendar-month"></div>
      <label class="date-jump" for="publication-date">Jump to date<input id="publication-date" type="date"></label>
      <button type="button" id="all-dates" class="all-dates" aria-pressed="true">All dates</button>
      <p class="calendar-note">Dates use the publication or preprint date recorded in the catalog.</p>
    </aside>
    <section class="results" aria-labelledby="results-heading">
      <h2 id="results-heading">All publication dates</h2>
      <div class="filters">
        <label class="search-label" for="q">Search papers<input id="q" type="search" placeholder="Title, journal, disease or method"></label>
        <label for="domain">Research area<select id="domain">
          <option value="">All research areas</option>
          <option>Medical AI</option><option>Medical Agent</option><option>Ophthalmic AI</option><option>Ophthalmic Agent</option>
        </select></label>
      </div>
      <p id="result-count" class="muted" role="status" aria-live="polite"></p>
      <div class="papers" id="papers">{''.join(articles)}</div>
      <p id="empty-results" class="notice" hidden>No papers match this date and these filters in the current archive. Try another date or clear your filters.</p>
      <button type="button" id="show-more" class="show-more"{' hidden' if len(papers) <= 50 else ''}>Show more papers</button>
      <noscript><p class="notice">Enable JavaScript to use the calendar, search and complete archive.</p></noscript>
    </section>
  </div>
  <details class="audit">
    <summary>{state} · {complete}/{total} queries completed</summary>
    <p>Search completion describes retrieval, not coverage of all published literature. Each row records a query from the latest scan.</p>
    <div class="scroll"><table>
      <thead><tr><th>Retrieval index</th><th>Query</th><th>Date field</th><th>Matches</th><th>Retrieved</th><th>Status</th><th>Cursor / error</th></tr></thead>
      <tbody>{audit_rows}</tbody>
    </table></div>
  </details>
  <footer>Automated screening priorities are not evidence quality ratings.
    <nav aria-label="Download data"><a href="./data/catalog.json">Full catalog</a><a href="./data/latest.json">Latest retrieval report</a><a href="./data/history.json">Run history</a></nav>
  </footer>
</main>
</body>
</html>'''
    (output_dir / "index.html").write_text(page, encoding="utf-8")
