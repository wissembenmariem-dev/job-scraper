from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

import yaml

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
REQUEST_TIMEOUT = 25


@dataclass(frozen=True)
class Filters:
    keywords: List[str] = field(default_factory=list)
    exclude_keywords: List[str] = field(default_factory=list)
    locations: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class Config:
    filters: Filters
    sources: Dict[str, List[Dict[str, Any]]]
    categories: Dict[str, List[str]]
    close_after_days: int
    timezone: str


def load_config(path: str | os.PathLike | None = None) -> Config:
    path = Path(path or os.environ.get("SOURCES_FILE", "sources.yaml"))
    if not path.exists():
        path = Path("sources.example.yaml")
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    f = raw.get("filters", {})
    return Config(
        filters=Filters(
            keywords=f.get("keywords", []),
            exclude_keywords=f.get("exclude_keywords", []),
            locations=f.get("locations", []),
        ),
        sources={k: raw.get("sources", {}).get(k, []) or [] for k in ("workday", "oracle_hcm", "html")},
        categories=raw.get("categories", {}),
        close_after_days=int(raw.get("close_after_days", 2)),
        timezone=os.environ.get("TZ", raw.get("timezone", "UTC")),
    )
