from __future__ import annotations

import logging
from typing import Any, Dict, List

import requests

from ..config import REQUEST_TIMEOUT, USER_AGENT

log = logging.getLogger(__name__)

PAGE_SIZE = 25
MAX_PAGES = 20


def fetch(source: Dict[str, Any]) -> List[Dict[str, Any]]:
    base, site, company = source["base"].rstrip("/"), source["site"], source["company"]
    endpoint = f"{base}/hcmRestApi/resources/latest/recruitingCEJobRequisitions"
    board_url = f"{base}/hcmUI/CandidateExperience/en/sites/{site}"
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json", "Referer": board_url}

    jobs: List[Dict[str, Any]] = []
    offset = 0
    for _ in range(MAX_PAGES):
        params = {
            "onlyData": "true",
            "expand": "requisitionList.secondaryLocations",
            "finder": f"findReqs;siteNumber={site},limit={PAGE_SIZE},offset={offset},sortBy=POSTING_DATES_DESC",
        }
        try:
            r = requests.get(endpoint, headers=headers, params=params, timeout=REQUEST_TIMEOUT)
            r.raise_for_status()
            items = r.json().get("items", [])
        except (requests.RequestException, ValueError) as e:
            log.warning("[%s] Oracle HCM page offset=%d failed: %s", company, offset, e)
            break

        reqs = items[0].get("requisitionList", []) if items else []
        if not reqs:
            break

        for req in reqs:
            req_id = req.get("Id") or req.get("ReqId") or ""
            posted = req.get("PostedDate")
            jobs.append({
                "company": company,
                "title": str(req.get("Title") or "").strip(),
                "location": str(req.get("PrimaryLocation") or "").strip(),
                "url": f"{board_url}/job/{req_id}",
                "external_id": f"oracle::{req_id}",
                "posted_date": posted[:10] if posted else None,
                "source_type": "Oracle HCM",
            })

        offset += PAGE_SIZE
        if offset >= items[0].get("TotalJobsCount", len(reqs)):
            break

    return jobs
