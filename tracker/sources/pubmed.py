"""PubMed: distinct EPDAT, EDAT and CRDT windows; ESearch pagination + EFetch."""
from __future__ import annotations

import os
import time
import xml.etree.ElementTree as ET
from datetime import date
from typing import Any

from tracker.core import Paper, make_paper
from tracker.http import audit, get

ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
FAMILIES = {
    "medical_models": "(medical[tiab] OR clinical[tiab] OR healthcare[tiab] OR radiology[tiab] OR hospital[tiab]) AND (artificial intelligence[tiab] OR machine learning[tiab] OR deep learning[tiab] OR large language model[tiab] OR foundation model[tiab] OR multimodal[tiab])",
    "medical_agents": "(clinical[tiab] OR healthcare[tiab] OR EHR[tiab] OR medicine[tiab]) AND (agent[tiab] OR agentic[tiab] OR LLM[tiab] OR reasoning[tiab] OR tool use[tiab] OR AI safety[tiab])",
    "eye_models": "(ophthalmology[tiab] OR retinal[tiab] OR retina[tiab] OR fundus[tiab] OR OCT[tiab] OR glaucoma[tiab] OR diabetic retinopathy[tiab] OR macular degeneration[tiab]) AND (artificial intelligence[tiab] OR deep learning[tiab] OR machine learning[tiab] OR vision language[tiab] OR foundation model[tiab])",
    "eye_agents": "(ophthalmology[tiab] OR retinal[tiab] OR fundus[tiab] OR glaucoma[tiab] OR OCT[tiab]) AND (large language model[tiab] OR agent[tiab] OR agentic[tiab] OR multimodal[tiab] OR clinical reasoning[tiab])",
}
FIELDS = ("epdat", "edat", "crdt")


def contents(elem: ET.Element | None) -> str:
    return " ".join(" ".join(elem.itertext()).split()) if elem is not None else ""


def parse_efetch(xml: str, query_id: str) -> list[Paper]:
    root = ET.fromstring(xml)
    items: list[Paper] = []
    for article in root.findall(".//PubmedArticle"):
        pmid = contents(article.find(".//MedlineCitation/PMID"))
        title = contents(article.find(".//Article/ArticleTitle"))
        if not pmid or not title:
            continue
        abstract = " ".join(contents(x) for x in article.findall(".//Article/Abstract/AbstractText"))
        authors: list[str] = []
        for person in article.findall(".//Article/AuthorList/Author"):
            name = " ".join(filter(None, [contents(person.find("ForeName")), contents(person.find("LastName"))]))
            if name:
                authors.append(name)
        doi = ""
        for aid in article.findall(".//PubmedData/ArticleIdList/ArticleId"):
            if aid.get("IdType") == "doi":
                doi = contents(aid)
        year, month, day = "", "01", "01"
        article_date = article.find(".//Article/ArticleDate")
        published = article_date if article_date is not None else article.find(".//Article/Journal/JournalIssue/PubDate")
        if published is not None:
            year = contents(published.find("Year"))
            month = contents(published.find("Month")) or "01"
            day = contents(published.find("Day")) or "01"
        if month and not month.isdigit():
            from datetime import datetime
            try:
                month = str(datetime.strptime(month[:3], "%b").month)
            except ValueError:
                month = "01"
        try:
            pub = date(int(year), int(month), int(day)).isoformat()
        except (ValueError, TypeError):
            pub = ""
        venue = contents(article.find(".//Article/Journal/Title"))
        paper = make_paper(title=title, abstract=abstract, authors=authors, url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/", published=pub, source="pubmed", source_id=pmid, doi=doi, venue=venue, review_status="peer_reviewed")
        paper.matched_queries = [query_id]
        items.append(paper)
    return items


def scan(session: Any, start: date, end: date, max_items: int = 5000) -> tuple[list[Paper], list[dict]]:
    papers: list[Paper] = []
    reports: list[dict] = []
    ident: dict[str, Paper] = {}
    for family, expression in FAMILIES.items():
        for field in FIELDS:
            qid = family + "_" + field
            query = f"({expression}) AND ({start:%Y/%m/%d}:{end:%Y/%m/%d}[{field}])"
            ids: list[str] = []
            total: int | None = None
            error = ""
            offset = 0
            try:
                while True:
                    r = get(session, ESEARCH, {"db": "pubmed", "term": query, "retmode": "json", "retstart": offset, "retmax": 500, "tool": "MedicalAITracker", **({"email": os.getenv("CONTACT_EMAIL")} if os.getenv("CONTACT_EMAIL") else {})})
                    d = r.json()["esearchresult"]
                    total = int(d["count"])
                    page = d.get("idlist", [])
                    ids.extend(page)
                    offset += len(page)
                    if offset >= total or not page or offset >= max_items:
                        break
                    time.sleep(0.38)
                for pos in range(0, len(ids), 150):
                    r = get(session, EFETCH, {"db": "pubmed", "id": ",".join(ids[pos:pos+150]), "rettype": "xml", "retmode": "xml", "tool": "MedicalAITracker", **({"email": os.getenv("CONTACT_EMAIL")} if os.getenv("CONTACT_EMAIL") else {})})
                    for p in parse_efetch(r.text, qid):
                        if p.source_id not in ident:
                            ident[p.source_id] = p
                        else:
                            ident[p.source_id].matched_queries.append(qid)
                    time.sleep(0.38)
            except Exception as exc:
                error = str(exc)[:350]
            # fetched = ESearch IDs, not number of successfully parsed abstracts; never conflate.
            complete = (not error and total is not None and len(ids) >= total and all(x in ident for x in ids))
            reports.append(audit("pubmed", qid, query, field, f"{start}/{end}", total=total, fetched=len(ids), complete=complete, next_cursor=None if complete else len(ids), error=error, candidate_ids=list(ids)[:3000]))
    papers = list(ident.values())
    return papers, reports
