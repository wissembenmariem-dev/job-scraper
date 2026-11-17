from __future__ import annotations

import hashlib
import re
import unicodedata
from typing import Any, Dict, Iterable, List, Optional

from .config import Filters

SENIORITY_PATTERNS = [
    ("Intern", r"\b(intern|internship|trainee|graduate|apprentice)\b"),
    ("Director", r"\b(director|head of|vp|vice president|chief)\b"),
    ("Manager", r"\bmanager\b"),
    ("Lead", r"\b(lead|principal|staff)\b"),
    ("Senior", r"\b(senior|sr)\b"),
    ("Junior", r"\b(junior|jr|entry[\s-]?level)\b"),
]


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFD", text or "")
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", text.lower()).strip()


def _contains(haystack: str, terms: Iterable[str]) -> bool:
    for term in terms:
        t = normalize_text(term)
        if t and re.search(rf"(?<!\w){re.escape(t)}(?!\w)", haystack):
            return True
    return False


def matches_location(job: Dict[str, Any], locations: List[str]) -> bool:
    if not locations:
        return True
    return _contains(normalize_text(f"{job.get('location', '')} {job.get('title', '')}"), locations)


def matches_keywords(title: str, filters: Filters) -> bool:
    t = normalize_text(title)
    if not t or _contains(t, filters.exclude_keywords):
        return False
    return not filters.keywords or _contains(t, filters.keywords)


def classify_seniority(title: str) -> Optional[str]:
    t = normalize_text(title)
    return next((label for label, pattern in SENIORITY_PATTERNS if re.search(pattern, t)), None)


def classify_category(title: str, categories: Dict[str, List[str]]) -> str:
    t = normalize_text(title)
    return next((name for name, terms in categories.items() if _contains(t, terms)), "Other")


def external_id(job: Dict[str, Any]) -> str:
    company = job["company"]
    if job.get("external_id"):
        return f"{company}::{job['external_id']}"[:1000]
    url = (job.get("url") or "").split("?")[0].rstrip("/")
    key = url or f"{normalize_text(job['title'])}|{normalize_text(job.get('location', ''))}"
    return f"{company}::{hashlib.sha1(f'{company}|{key}'.encode()).hexdigest()}"


def normalize_and_filter(raw_jobs: Iterable[Dict[str, Any]], filters: Filters, categories: Dict[str, List[str]]) -> List[Dict[str, Any]]:
    out, seen = [], set()
    for j in raw_jobs:
        job = {**j, "title": (j.get("title") or "").strip(), "location": (j.get("location") or "").strip(), "url": (j.get("url") or "").strip()}
        if not job["title"] or not matches_location(job, filters.locations) or not matches_keywords(job["title"], filters):
            continue
        job["external_id"] = external_id(job)
        if job["external_id"] in seen:
            continue
        seen.add(job["external_id"])
        job["seniority"] = classify_seniority(job["title"])
        job["category"] = classify_category(job["title"], categories)
        out.append(job)
    return out
