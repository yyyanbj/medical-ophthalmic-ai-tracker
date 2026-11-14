"""Requests session with bounded retries, an honest timeout, and provenance."""
from __future__ import annotations

import os
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def client() -> requests.Session:
    s = requests.Session()
    contact = os.getenv("CONTACT_EMAIL", "").strip()
    agent = "medical-ophthalmic-ai-tracker/1.0 (+https://github.com/yyyanbj/medical-ophthalmic-ai-tracker)"
    if contact:
        agent += f" (contact: {contact})"
    s.headers.update({"User-Agent": agent})
    retry = Retry(total=4, backoff_factor=1.0, status_forcelist=(429, 500, 502, 503, 504), allowed_methods=frozenset({"GET"}), respect_retry_after_header=True)
    s.mount("https://", HTTPAdapter(max_retries=retry))
    return s


def get(session: requests.Session, url: str, params: dict | None = None) -> requests.Response:
    r = session.get(url, params=params, timeout=(10, 40))
    r.raise_for_status()
    return r


def audit(source: str, query_id: str, query: str, date_field: str, window: str, *, total=None, fetched=0, complete=False, next_cursor=None, error="", candidate_ids=None) -> dict:
    from .core import now_iso
    return {"source": source, "query_id": query_id, "query": query, "date_field": date_field, "window": window,
            "total": total, "fetched": fetched, "complete": complete, "next_cursor": next_cursor,
            "status": "failed" if error and not fetched else ("complete" if complete else "partial"),
            "error": error, "candidate_ids": candidate_ids or [], "checked_at": now_iso()}
