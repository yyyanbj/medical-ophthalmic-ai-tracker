"""arXiv Atom API: topic queries, submittedDate ranges and updated-date audit."""
from __future__ import annotations

import time
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from typing import Any
from tracker.core import Paper, make_paper
from tracker.http import audit, get

ENDPOINT = "https://export.arxiv.org/api/query"
ATOM = "{http://www.w3.org/2005/Atom}"
OPEN = "{http://a9.com/-/spec/opensearch/1.1/}"
QUERIES = {
    "medical_models": '(all:medical OR all:clinical OR all:healthcare OR all:radiology) AND (all:"large language model" OR all:"foundation model" OR all:"machine learning" OR all:"deep learning" OR all:multimodal)',
    "medical_agents": '(all:medical OR all:clinical OR all:healthcare) AND (all:agentic OR all:"AI agent" OR all:reasoning OR all:"tool use")',
    "eye_models": '(all:ophthalmology OR all:retina OR all:fundus OR all:OCT OR all:glaucoma OR all:"diabetic retinopathy" OR all:"macular degeneration") AND (all:"artificial intelligence" OR all:"deep learning" OR all:multimodal OR all:"foundation model")',
    "eye_agents": '(all:ophthalmology OR all:retina OR all:fundus OR all:glaucoma OR all:OCT) AND (all:agent OR all:agentic OR all:"large language model" OR all:reasoning)',
}


def parse_atom(content: str, query_id: str) -> tuple[list[Paper], int | None]:
    root = ET.fromstring(content)
    total_text = root.findtext(OPEN + "totalResults")
    total = int(total_text) if total_text and total_text.isdigit() else None
    papers: list[Paper] = []
    for entry in root.findall(ATOM + "entry"):
        title = " ".join((entry.findtext(ATOM+"title") or "").split())
        identifier = entry.findtext(ATOM+"id") or ""
        source_id = identifier.rsplit("/", 1)[-1].split("v")[0]
        if not title or not source_id:
            continue
        authors = [a.findtext(ATOM+"name") or "" for a in entry.findall(ATOM+"author")]
        published = (entry.findtext(ATOM+"published") or "")[:10]
        updated = (entry.findtext(ATOM+"updated") or "")[:10]
        abstract = " ".join((entry.findtext(ATOM+"summary") or "").split())
        doi = ""
        for link in entry.findall(ATOM+"link"):
            if link.get("title") == "doi":
                doi = link.get("href", "")
        paper = make_paper(title=title, abstract=abstract, authors=authors, url=f"https://arxiv.org/abs/{source_id}", published=published, source="arxiv", source_id=source_id, doi=doi, updated=updated, venue="arXiv", review_status="preprint")
        paper.matched_queries = [query_id]
        papers.append(paper)
    return papers, total


def scan(session: Any, start: date, end: date, max_items: int = 3000) -> tuple[list[Paper], list[dict]]:
    all_papers: dict[str, Paper] = {}
    audit_rows: list[dict] = []
    utc_start = start.strftime("%Y%m%d") + "0000"
    utc_end = end.strftime("%Y%m%d") + "2359"
    for name, expression in QUERIES.items():
        for mode in ("submitted", "updated"):
            # The API supports submittedDate range. For updates the API supports *sort* by
            # lastUpdatedDate; inspect entry.updated rather than claiming a range filter.
            qid = f"{name}_{mode}"
            query = (expression + f" AND submittedDate:[{utc_start} TO {utc_end}]") if mode == "submitted" else expression
            offset = 0
            total = None
            error = ""
            fetched = 0
            batch = []
            accepted_ids: list[str] = []
            try:
                while True:
                    params = {"search_query": query, "start": offset, "max_results": 100, "sortBy": "submittedDate" if mode == "submitted" else "lastUpdatedDate", "sortOrder": "descending"}
                    content = get(session, ENDPOINT, params).text
                    batch, count = parse_atom(content, qid)
                    if count is not None:
                        total = count
                    if not batch:
                        break
                    fetched += len(batch)
                    for p in batch:
                        if mode == "updated" and not (start.isoformat() <= p.updated <= end.isoformat()):
                            continue
                        accepted_ids.append(p.source_id)
                        if p.source_id in all_papers:
                            all_papers[p.source_id].matched_queries.append(qid)
                        else:
                            all_papers[p.source_id] = p
                    offset += len(batch)
                    # Updated list is descending by updated; old entries bound the window.
                    if mode == "updated" and batch[-1].updated and batch[-1].updated < start.isoformat():
                        break
                    if (total is not None and offset >= total) or fetched >= max_items:
                        break
                    time.sleep(3.1)
            except Exception as exc:
                error = str(exc)[:350]
            if mode == "submitted":
                complete = not error and total is not None and fetched >= total
            else:
                complete = not error and ((total is not None and fetched >= total) or (bool(batch) and batch[-1].updated < start.isoformat()))
            # In updated mode upstream total is ALL-TIME matching works, not a window
            # count.  Only report an exact date-window count once sorted traversal has
            # passed the window boundary; otherwise keep it unknown.
            row = audit("arxiv", qid, query, "submittedDate" if mode == "submitted" else "sortBy:lastUpdatedDate; check updated", f"{start}/{end}", total=total if mode == "submitted" else (len(accepted_ids) if complete else None), fetched=fetched if mode == "submitted" else len(accepted_ids), complete=complete, next_cursor=None if complete else offset, error=error, candidate_ids=accepted_ids[:3000])
            if mode == "updated":
                row["scanned_all_time_sorted"] = fetched
                row["upstream_all_time_count"] = total
            audit_rows.append(row)
    return list(all_papers.values()), audit_rows
