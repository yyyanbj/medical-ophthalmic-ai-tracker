"""Journal DOI index coverage using Crossref per-ISSN online publication date.

IMPORTANT: Crossref is an index/alternate source, not proof that a journal's
entire online-first site was crawled. Audit rows say exactly that.
"""
from __future__ import annotations

from datetime import date
from typing import Any

from tracker.core import Paper, make_paper
from tracker.http import audit, get

ISSNS = {
    "Nature Medicine": "1078-8956",
    "npj Digital Medicine": "2398-6352",
    "The Lancet Digital Health": "2589-7500",
    "JAMA": "0098-7484",
    "JAMA Ophthalmology": "2168-6165",
    "Ophthalmology": "0161-6420",
    "Ophthalmology Retina": "2468-6530",
    "Ophthalmology Science": "2666-9145",
    "Investigative Ophthalmology & Visual Science": "0146-0404",
    "Translational Vision Science & Technology": "2164-2591",
    "British Journal of Ophthalmology": "0007-1161",
    "American Journal of Ophthalmology": "0002-9394",
    "IEEE Transactions on Medical Imaging": "0278-0062",
    "Medical Image Analysis": "1361-8415",
    "Artificial Intelligence in Medicine": "0933-3657",
    "PLOS Digital Health": "2767-3170",
}


def publication_date(item: dict) -> str:
    date_block = item.get("published-online") or item.get("published") or item.get("created") or {}
    parts = date_block.get("date-parts", [[]])[0]
    if not parts:
        return ""
    return "-".join([str(parts[0]), str(parts[1]).zfill(2) if len(parts)>1 else "01", str(parts[2]).zfill(2) if len(parts)>2 else "01"])


def parse_work(item: dict, query_id: str) -> Paper | None:
    title = " ".join(item.get("title", [""])[0].split()) if item.get("title") else ""
    doi = item.get("DOI", "")
    if not doi or not title:
        return None
    authors = [" ".join(filter(None, [a.get("given", ""), a.get("family", "")])) for a in item.get("author", [])]
    venue = item.get("container-title", [""])[0] if item.get("container-title") else query_id
    abstract = item.get("abstract", "")  # Crossref sometimes supplies JATS XML.
    import re, html
    abstract = " ".join(html.unescape(re.sub(r"<[^>]*>", " ", abstract)).split())
    p = make_paper(title=title, abstract=abstract, authors=authors, url=item.get("URL", "https://doi.org/"+doi),
                   published=publication_date(item), source="crossref", source_id=doi, doi=doi, venue=venue, review_status="peer_reviewed")
    p.matched_queries = [query_id]
    return p


def scan(session: Any, start: date, end: date, max_items_per_journal: int = 400) -> tuple[list[Paper], list[dict]]:
    papers: dict[str, Paper] = {}
    reports: list[dict] = []
    for journal, issn in ISSNS.items():
        offset = 0
        total = None
        error = ""
        fetched = 0
        try:
            while True:
                params = {"filter": f"from-online-pub-date:{start.isoformat()},until-online-pub-date:{end.isoformat()}",
                          "rows": 100, "offset": offset, **({"mailto": __import__("os").getenv("CONTACT_EMAIL")} if __import__("os").getenv("CONTACT_EMAIL") else {})}
                body = get(session, f"https://api.crossref.org/journals/{issn}/works", params).json().get("message", {})
                total = int(body.get("total-results", 0))
                items = body.get("items", [])
                fetched += len(items)
                for item in items:
                    p = parse_work(item, journal)
                    if p:
                        papers[p.source_id.lower()] = p
                offset += len(items)
                if not items or offset >= total or offset >= max_items_per_journal:
                    break
        except Exception as exc:
            error = str(exc)[:350]
        complete = not error and total is not None and fetched >= total
        reports.append(audit("crossref-journal", journal, f"Crossref ISSN={issn}; from-online-pub-date={start}; until-online-pub-date={end}", "Crossref indexed online publication", f"{start}/{end}", total=total, fetched=fetched, complete=complete, next_cursor=None if complete else offset, error=error, candidate_ids=[p.source_id for p in papers.values() if journal in p.matched_queries][:1000]))
    return list(papers.values()), reports
