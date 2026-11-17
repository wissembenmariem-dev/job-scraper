from __future__ import annotations

import logging
import re
from datetime import date, timedelta
from typing import Any, Dict, List, Optional

import requests

from ..config import REQUEST_TIMEOUT, USER_AGENT

log = logging.getLogger(__name__)

PAGE_SIZE = 20
MAX_PAGES = 20


def parse_posted_on(raw: Optional[str], today: Optional[date] = None) -> Optional[str]:
    if not raw:
        return None
    today = today or date.today()
    s = str(raw).strip().lower().replace("posted", "").strip()
    if s in {"", "today"}:
        return today.isoformat()
    if s == "yesterday":
        return (today - timedelta(days=1)).isoformat()
    m = re.match(r"(\d+)\+?\s+days?\s+ago", s)
    if m:
        return (today - timedelta(days=int(m.group(1)))).isoformat()
    m = re.match(r"(\d+)\+?\s+months?\s+ago", s)
    if m:
        return (today - timedelta(days=30 * int(m.group(1)))).isoformat()
    m = re.match(r"\d{4}-\d{2}-\d{2}", s)
    return m.group(0) if m else None


def fetch(source: Dict[str, Any]) -> List[Dict[str, Any]]:
    host, tenant, site, company = source["host"], source["tenant"], source["site"], source["company"]
    board_url = source.get("board_url", f"https://{host}/{site}").rstrip("/")
    endpoint = f"https://{host}/wday/cxs/{tenant}/{site}/jobs"
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Origin": f"https://{host}",
        "Referer": board_url,
    }

    jobs: List[Dict[str, Any]] = []
    offset = 0
    for _ in range(MAX_PAGES):
        payload = {"appliedFacets": {}, "limit": PAGE_SIZE, "offset": offset, "searchText": source.get("search", "")}
        try:
            r = requests.post(endpoint, json=payload, headers=headers, timeout=REQUEST_TIMEOUT)
            r.raise_for_status()
            data = r.json()
        except (requests.RequestException, ValueError) as e:
            log.warning("[%s] Workday page offset=%d failed: %s", company, offset, e)
            break

        postings = data.get("jobPostings", [])
        if not postings:
            break

        for p in postings:
            path = p.get("externalPath", "")
            location = (p.get("locationsText") or "").strip()
            if re.match(r"^\d+\s+Locations?$", location, re.I):
                m = re.search(r"/job/([^/]+)/", path)
                location = m.group(1).replace("-", " ") if m else location
            jobs.append({
                "company": company,
                "title": (p.get("title") or "").strip(),
                "location": location,
                "url": f"{board_url}{path}" if path else board_url,
                "external_id": (p.get("bulletFields") or [""])[0] or path,
                "posted_date": parse_posted_on(p.get("postedOn")),
                "source_type": "Workday",
            })

        offset += PAGE_SIZE
        if offset >= data.get("total", 0):
            break

    return jobs
