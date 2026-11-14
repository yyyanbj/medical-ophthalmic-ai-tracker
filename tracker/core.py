"""Shared, dependency-light paper representation, matching and audit rules."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

AI = re.compile(r"\b(?:AI|artificial intelligence|machine learning|deep learning|generative ai|generative model|foundation model|large language model|language model|llm|multi.?modal|vision.language|transformer|neural network|computer vision|agentic|multi.agent|autonomous agent|reinforcement learning|automated segmentation|deep neural|convolutional network|image classification|ai.assisted|ai.based|gpt.[3456]|clinical decision support)\b", re.I)
EYE = re.compile(r"\b(?:ophthalm\w*|retin\w*|fundus|fundoscopy|optical coherence tomography|\bOCT\b|glaucoma|macular degeneration|\bAMD\b|diabetic retinopathy|\bDR\b|ocular|optomet\w*|optic disc|optic nerve|vitreous|cornea\w*|eye disease|visual acuity|cataract\w*)\b", re.I)
MEDICAL = re.compile(r"\b(?:medic\w*|clinic\w*|health\w*|patient\w*|hospitals?|electronic health record|\bEHR\b|radiolog\w*|patholog\w*|dermatolog\w*|cardiolog\w*|oncolog\w*|cancer|intensive care|\bICU\b|disease|diagnos\w*|therap\w*|treatment|surg\w*|clinical trial|pharmac\w*|biomedical|neonat\w*|sepsis|\bECMO\b|triage|medical imaging)\b", re.I)
AGENT = re.compile(r"\b(?:agentic|multi.agent|ai agent|autonomous agent|tool.calling|tool.use|clinical workflow|reasoning agent|multiagent)\b", re.I)
NOVEL = re.compile(r"\b(?:prospective|multicenter|multi.center|external validation|randomi[sz]ed|clinical trial|benchmark|foundation model|agentic|safety|hallucination|dataset shift|bias|fairness|novel)\b", re.I)


def norm_title(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).casefold()
    return re.sub(r"[^a-z0-9]+", "", value)


def norm_doi(value: str) -> str:
    return re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:)\s*", "", value.strip(), flags=re.I).lower()


def classify(title: str, abstract: str = "") -> tuple[str, int, str]:
    text = f"{title} {abstract[:25000]}"
    if not AI.search(text):
        return "out_of_scope", 0, "No explicit AI/ML/agent method detected"
    if EYE.search(text):
        domain = "Ophthalmic Agent" if AGENT.search(text) else "Ophthalmic AI"
    elif MEDICAL.search(text):
        domain = "Medical Agent" if AGENT.search(text) else "Medical AI"
    else:
        return "out_of_scope", 0, "No medical/ophthalmic context detected"
    score = 1 + int(bool(NOVEL.search(text))) + int(bool(AGENT.search(text)))
    return domain, score, "Keyword candidate only; requires reading and human/AI evidence verification"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class Paper:
    title: str
    abstract: str
    authors: list[str]
    url: str
    published: str
    source: str
    source_id: str
    doi: str = ""
    updated: str = ""
    venue: str = ""
    review_status: str = "unknown"
    version: str = ""
    sources: list[str] = field(default_factory=list)
    matched_queries: list[str] = field(default_factory=list)
    domain: str = ""
    score: int = 0
    rationale: str = ""
    first_seen: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def make_paper(**kwargs: Any) -> Paper:
    p = Paper(**kwargs)
    p.doi = norm_doi(p.doi)
    p.sources = [p.source]
    p.first_seen = now_iso()
    p.domain, p.score, p.rationale = classify(p.title, p.abstract)
    return p


def paper_key(p: dict[str, Any]) -> str:
    doi = norm_doi(p.get("doi") or "")
    if doi:
        return "doi:" + doi
    source_id = p.get("source_id") or ""
    if source_id:
        return ("arxiv:" if p.get("source") == "arxiv" else p.get("source", "source") + ":") + source_id.lower()
    return "title:" + norm_title(p.get("title", ""))


def combine(existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    """Keep provenance, prefer more informative metadata, preserve oldest public date."""
    merged = dict(existing)
    for field_name in ("sources", "matched_queries"):
        merged[field_name] = sorted(set(existing.get(field_name, []) + incoming.get(field_name, [])))
    for name in ("abstract", "authors", "venue", "url", "doi", "updated", "version"):
        old, new = merged.get(name), incoming.get(name)
        if new and (not old or (name == "abstract" and len(str(new)) > len(str(old)))):
            merged[name] = new
    if incoming.get("review_status") == "peer_reviewed":
        merged["review_status"] = "peer_reviewed"
        merged["venue"] = incoming.get("venue") or merged.get("venue", "")
        merged["url"] = incoming.get("url") or merged.get("url", "")
    dates = [d for d in (merged.get("published"), incoming.get("published")) if d]
    if dates:
        merged["published"] = min(dates)
    merged["updated"] = max([d for d in (merged.get("updated"), incoming.get("updated")) if d] or [""])
    if incoming.get("domain", "") not in ("", "out_of_scope"):
        merged["domain"] = incoming["domain"]
    merged["score"] = max(int(existing.get("score") or 0), int(incoming.get("score") or 0))
    return merged


def merge_catalog(catalog: dict[str, dict], items: list[Paper]) -> tuple[list[str], int]:
    """Deduplicate on DOI, then *exact normalized title* across all sources."""
    new_keys: list[str] = []
    updated = 0
    title_to_key = {norm_title(v.get("title", "")): k for k, v in catalog.items() if v.get("title")}
    for p in items:
        item = p.as_dict()
        if item["domain"] == "out_of_scope":
            continue
        key = paper_key(item)
        prev = title_to_key.get(norm_title(item["title"]))
        existing_key = key if key in catalog else prev
        if existing_key is not None:
            old = catalog[existing_key]
            merged = combine(old, item)
            if merged != old:
                updated += 1
            catalog[existing_key] = merged
        else:
            catalog[key] = item
            new_keys.append(key)
            title_to_key[norm_title(item["title"])] = key
    return new_keys, updated
