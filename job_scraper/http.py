from __future__ import annotations

import logging
from typing import Optional

import requests
from bs4 import BeautifulSoup

from .config import REQUEST_TIMEOUT, USER_AGENT

log = logging.getLogger(__name__)


def get_soup(url: str) -> Optional[BeautifulSoup]:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    try:
        r = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
    except requests.RequestException as e:
        log.warning("GET %s failed: %s", url, e)
        return None
    if r.status_code != 200:
        log.warning("GET %s returned %d", url, r.status_code)
        return None
    return BeautifulSoup(r.text, "lxml")
