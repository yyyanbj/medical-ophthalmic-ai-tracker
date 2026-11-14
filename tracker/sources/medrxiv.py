"""medRxiv official metadata API with alternate official host and cursor audit."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from tracker.core import Paper, make_paper, norm_doi
from tracker.http import audit, get

HOSTS = ("https://api.medrxiv.org/details", "https://api.biorxiv.org/details")


def parse_records(payload: dict) -> tuple[list[Paper], int | None]:
    rows: list[Paper] = []
    message = (payload.get("messages") or [{}])[0]
    try:
        count = int(message.get("count"))
    except (ValueError, TypeError):
        count = None
    for item in payload.get("collection", []):
        doi = norm_doi(item.get("doi", ""))
        title = " ".join(item.get("title", "").split())
        if not doi or not title:
            continue
        abstract = " ".join(item.get("abstract", "").split())
        authors = [x.strip() for x in item.get("authors", "").split(";") if x.strip()]
        publication = item.get("published", "")
        version = str(item.get("version", ""))
        p = make_paper(title=title, abstract=abstract, authors=authors, url="https://doi.org/"+doi,
                       published=item.get("date", "")[:10], source="medrxiv", source_id=doi,
                       doi=doi, updated=item.get("date", "")[:10], version=version,
                       venue=item.get("category", "medRxiv"), review_status="preprint")
        if publication and publication != "NA":
            # The metadata may supply a published DOI but this does not by itself
            # establish that we have checked the journal article.
            p.rationale += f"; publication linkage reported by medRxiv: {publication}"
        rows.append(p)
    return rows, count


def scan(session: Any, start: date, end: date, max_items: int = 8000) -> tuple[list[Paper], list[dict]]:
    papers: dict[str, Paper] = {}
    reports: list[dict] = []
    for host in HOSTS:
        cursor = 0
        count: int | None = None
        error = ""
        last_len = 0
        try:
            while True:
                url = f"{host}/medrxiv/{start.isoformat()}/{end.isoformat()}/{cursor}/json"
                data = get(session, url).json()
                page, found_count = parse_records(data)
                if found_count is not None:
                    count = found_count
                raw_len = len(data.get("collection", []))
                last_len = raw_len
                for paper in page:
                    old = papers.get(paper.source_id)
                    if not old or (paper.version.isdigit() and (not old.version.isdigit() or int(paper.version) > int(old.version))):
                        papers[paper.source_id] = paper
                cursor += raw_len
                if not raw_len or (count is not None and cursor >= count) or cursor >= max_items:
                    break
                if count is None and raw_len < 30:
                    # Without count metadata no defensible proof of completion.
                    break
        except Exception as exc:
            error = str(exc)[:350]
        complete = not error and count is not None and cursor >= count
        reports.append(audit("medrxiv", host, f"{host}/medrxiv/{start}/{end}/{{cursor}}/json", "posted_date; version", f"{start}/{end}", total=count, fetched=cursor, complete=complete, next_cursor=None if complete else cursor, error=error, candidate_ids=list(papers)[:3000]))
        if complete:
            break  # Backup host isn't needed when primary is fully covered.
    return list(papers.values()), reports


def check_versions(session: Any, known: dict[str, dict], today: date, limit: int = 70) -> tuple[list[Paper], list[dict]]:
    """Refresh known, recent medRxiv DOIs for versions without re-downloading 30 days globally."""
    start = today - timedelta(days=30)
    recent = [(key, p) for key, p in known.items() if "medrxiv" in p.get("sources", [p.get("source")]) and (p.get("published") or "") >= start.isoformat()]
    reports: list[dict] = []
    refreshed: list[Paper] = []
    for key, p in recent[:limit]:
        doi = p.get("doi", "")
        if not doi:
            continue
        success = False
        error = ""
        for host in HOSTS:
            try:
                data = get(session, f"{host}/medrxiv/{doi}/na/json").json()
                batch, _ = parse_records(data)
                if batch:
                    latest = max(batch, key=lambda x: int(x.version) if x.version.isdigit() else 0)
                    if latest.version != p.get("version"):
                        refreshed.append(latest)
                    success = True
                    break
            except Exception as exc:
                error = str(exc)[:240]
        reports.append(audit("medrxiv", "refresh:"+doi, doi, "version by DOI", f"{start}/{today}", total=1, fetched=1 if success else 0, complete=success, error="" if success else error))
    if len(recent) > limit:
        reports.append(audit("medrxiv", "version_refresh_limit", "known DOI refresh", "last 30d", f"{start}/{today}", total=len(recent), fetched=limit, complete=False, next_cursor=limit, error="cap on known DOIs per run"))
    return refreshed, reports
