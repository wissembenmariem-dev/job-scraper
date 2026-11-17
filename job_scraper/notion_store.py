from __future__ import annotations

import logging
import os
import time
from datetime import datetime, date, timedelta
from typing import Any, Dict, List, Optional, Tuple

import requests

log = logging.getLogger(__name__)

NOTION_API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"


class NotionStore:
    def __init__(self, token: Optional[str] = None, database_id: Optional[str] = None):
        self.token = token or os.environ["NOTION_TOKEN"]
        self.database_id = (database_id or os.environ["NOTION_DATABASE_ID"]).replace("-", "")
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.token}",
            "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json",
        })

    def _request(self, method: str, path: str, json: Optional[dict] = None, retries: int = 3) -> dict:
        url = f"{NOTION_API}{path}"
        for attempt in range(retries):
            try:
                r = self.session.request(method, url, json=json, timeout=30)
            except requests.RequestException as e:
                log.warning("Notion %s %s network error: %s", method, path, e)
                time.sleep(2 ** attempt)
                continue

            if r.status_code == 429:
                wait = int(r.headers.get("Retry-After", "2"))
                log.warning("Notion rate-limited, sleeping %ds", wait)
                time.sleep(wait)
                continue
            if r.status_code >= 500:
                time.sleep(2 ** attempt)
                continue
            if r.status_code >= 400:
                raise RuntimeError(f"Notion {method} {path} -> {r.status_code}: {r.text[:500]}")
            return r.json()
        raise RuntimeError(f"Notion {method} {path}: exhausted retries")

    def load_existing(self) -> Dict[str, Dict[str, Any]]:
        index: Dict[str, Dict[str, Any]] = {}
        payload = {"page_size": 100}
        has_more = True
        next_cursor = None

        while has_more:
            body = dict(payload)
            if next_cursor:
                body["start_cursor"] = next_cursor
            data = self._request("POST", f"/databases/{self.database_id}/query", json=body)

            for page in data.get("results", []):
                props = page.get("properties", {})
                ext_id = _read_rich_text(props.get("External ID"))
                if not ext_id:
                    continue
                index[ext_id] = {
                    "page_id": page["id"],
                    "first_seen": _read_date(props.get("First Seen")),
                    "last_seen": _read_date(props.get("Last Seen")),
                    "status": _read_select(props.get("Status")),
                    "title": _read_title(props.get("Title")),
                    "company": _read_select(props.get("Company")),
                    "url": _read_url(props.get("URL")),
                }
            has_more = data.get("has_more", False)
            next_cursor = data.get("next_cursor")

        log.info("Notion: loaded %d existing pages", len(index))
        return index

    def upsert_job(
        self,
        job: Dict[str, Any],
        existing_index: Dict[str, Dict[str, Any]],
        today_iso: str,
    ) -> Tuple[str, bool, Optional[str]]:
        ext_id = job["external_id"]
        existing = existing_index.get(ext_id)

        if existing is None:
            props = self._job_to_properties(job, today_iso, is_new=True)
            body = {
                "parent": {"database_id": self.database_id},
                "properties": props,
            }
            self._request("POST", "/pages", json=body)
            log.info("  + created: [%s] %s", job["company"], job["title"])
            return ("created", True, None)

        was_closed = existing.get("status") == "Closed"
        new_status = "Active"
        props_update: Dict[str, Any] = {
            "Last Seen": {"date": {"start": today_iso}},
            "Status": {"select": {"name": new_status}},
            "Title": {"title": [{"text": {"content": (job.get("title") or "Untitled")[:2000]}}]},
            "Location": {"rich_text": [{"text": {"content": (job.get("location") or "")[:2000]}}]},
            "URL": {"url": job.get("url") or None},
            "Source": {"select": {"name": job["source_type"]}},
        }
        if was_closed:
            props_update["Closed Date"] = {"date": None}
        if job.get("category"):
            props_update["Category"] = {"select": {"name": job["category"]}}
        if job.get("seniority"):
            props_update["Seniority"] = {"select": {"name": job["seniority"]}}
        if job.get("posted_date"):
            props_update["Posted Date"] = {"date": {"start": job["posted_date"]}}
        self._request("PATCH", f"/pages/{existing['page_id']}", json={"properties": props_update})
        action = "reopened" if was_closed else "updated"
        return (action, False, existing.get("first_seen"))

    def close_stale(
        self,
        seen_external_ids: set,
        existing_index: Dict[str, Dict[str, Any]],
        today_iso: str,
        grace_days: int = 2,
    ) -> List[Dict[str, Any]]:
        today = datetime.fromisoformat(today_iso).date()
        threshold = today - timedelta(days=grace_days)
        closed: List[Dict[str, Any]] = []

        for ext_id, info in existing_index.items():
            if ext_id in seen_external_ids:
                continue
            if info.get("status") == "Closed":
                continue
            last_seen = info.get("last_seen")
            try:
                last_seen_date = datetime.fromisoformat(last_seen).date() if last_seen else None
            except ValueError:
                last_seen_date = None
            if last_seen_date is None or last_seen_date <= threshold:
                self._request(
                    "PATCH",
                    f"/pages/{info['page_id']}",
                    json={"properties": {
                        "Status": {"select": {"name": "Closed"}},
                        "Closed Date": {"date": {"start": today_iso}},
                    }},
                )
                closed.append(info | {"external_id": ext_id, "closed_date": today_iso})
                log.info("  - closed: [%s] %s", info.get("company"), info.get("title"))
        return closed


    @staticmethod
    def _job_to_properties(job: Dict[str, Any], today_iso: str, is_new: bool) -> Dict[str, Any]:
        props: Dict[str, Any] = {
            "Title": {"title": [{"text": {"content": (job.get("title") or "Untitled")[:2000]}}]},
            "Company": {"select": {"name": job["company"]}},
            "Location": {"rich_text": [{"text": {"content": (job.get("location") or "")[:2000]}}]},
            "URL": {"url": job.get("url") or None},
            "Status": {"select": {"name": "New" if is_new else "Active"}},
            "First Seen": {"date": {"start": today_iso}},
            "Last Seen": {"date": {"start": today_iso}},
            "Source": {"select": {"name": job["source_type"]}},
            "External ID": {"rich_text": [{"text": {"content": job["external_id"][:2000]}}]},
        }
        if job.get("category"):
            props["Category"] = {"select": {"name": job["category"]}}
        if job.get("seniority"):
            props["Seniority"] = {"select": {"name": job["seniority"]}}
        if job.get("posted_date"):
            props["Posted Date"] = {"date": {"start": job["posted_date"]}}
        return props


def _read_title(prop: Optional[dict]) -> str:
    if not prop:
        return ""
    return "".join(rt.get("plain_text", "") for rt in prop.get("title", []))


def _read_rich_text(prop: Optional[dict]) -> str:
    if not prop:
        return ""
    return "".join(rt.get("plain_text", "") for rt in prop.get("rich_text", []))


def _read_select(prop: Optional[dict]) -> Optional[str]:
    if not prop:
        return None
    sel = prop.get("select")
    return sel.get("name") if sel else None


def _read_url(prop: Optional[dict]) -> Optional[str]:
    if not prop:
        return None
    return prop.get("url")


def _read_date(prop: Optional[dict]) -> Optional[str]:
    if not prop:
        return None
    d = prop.get("date")
    return d.get("start") if d else None
