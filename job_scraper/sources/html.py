from __future__ import annotations

import re
from typing import Any, Dict, List
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from ..http import get_soup

JOB_LINK_HINTS = ("/job", "/career", "/vacan", "/opening", "/position", "/opport")


def _text(el: Tag | None) -> str:
    return re.sub(r"\s+", " ", el.get_text(" ", strip=True)) if el else ""


def parse_with_selectors(soup: BeautifulSoup, source: Dict[str, Any]) -> List[Dict[str, Any]]:
    sel = source["selectors"]
    jobs = []
    for item in soup.select(sel["item"]):
        title_el = item.select_one(sel.get("title", "a"))
        link_el = item.select_one(sel.get("link", "a[href]"))
        title = _text(title_el)
        if not title:
            continue
        location = _text(item.select_one(sel["location"])) if sel.get("location") else ""
        jobs.append(_job(source, title, location, urljoin(source["url"], link_el["href"]) if link_el else source["url"]))
    return jobs


def parse_generic(soup: BeautifulSoup, source: Dict[str, Any]) -> List[Dict[str, Any]]:
    jobs = []
    for a in soup.select("a[href]"):
        title = _text(a)
        href = urljoin(source["url"], a["href"])
        if not 8 <= len(title) <= 200 or not any(h in href.lower() for h in JOB_LINK_HINTS):
            continue
        parent = a.find_parent(["article", "li", "div", "tr"])
        location = _text(parent.find(class_=re.compile(r"location|city|place", re.I))) if parent else ""
        jobs.append(_job(source, title, location, href))
    return jobs


def _job(source: Dict[str, Any], title: str, location: str, url: str) -> Dict[str, Any]:
    return {
        "company": source["company"],
        "title": title,
        "location": location or source.get("default_location", ""),
        "url": url,
        "external_id": None,
        "posted_date": None,
        "source_type": "HTML",
    }


def fetch(source: Dict[str, Any]) -> List[Dict[str, Any]]:
    soup = get_soup(source["url"])
    if soup is None:
        return []
    parser = parse_with_selectors if source.get("selectors") else parse_generic
    return parser(soup, source)
