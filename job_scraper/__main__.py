from __future__ import annotations

import logging
import sys
import time
from datetime import datetime
from typing import Any, Callable, Dict, List
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

from . import digest
from .config import load_config
from .filters import normalize_and_filter
from .notion_store import NotionStore
from .sources import html, oracle_hcm, workday

ADAPTERS: Dict[str, Callable[[Dict[str, Any]], List[Dict[str, Any]]]] = {
    "workday": workday.fetch,
    "oracle_hcm": oracle_hcm.fetch,
    "html": html.fetch,
}

log = logging.getLogger("job_scraper")


def collect(sources: Dict[str, List[Dict[str, Any]]], errors: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    jobs: List[Dict[str, Any]] = []
    for kind, entries in sources.items():
        for source in entries:
            start = time.monotonic()
            try:
                found = ADAPTERS[kind](source)
                log.info("%-12s %-30s %4d jobs  %.1fs", kind, source["company"], len(found), time.monotonic() - start)
                jobs.extend(found)
            except Exception as e:
                log.error("%-12s %-30s failed: %s", kind, source.get("company", "?"), e)
                errors.append({"source": source.get("company", "?"), "error": str(e)})
    return jobs


def main() -> int:
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-5s %(message)s", datefmt="%H:%M:%S")
    cfg = load_config()
    now = datetime.now(ZoneInfo(cfg.timezone))
    today = now.date().isoformat()

    store = NotionStore()
    existing = store.load_existing()

    errors: List[Dict[str, str]] = []
    jobs = normalize_and_filter(collect(cfg.sources, errors), cfg.filters, cfg.categories)
    log.info("%d jobs after filtering", len(jobs))

    new_jobs, active_jobs, seen = [], [], set()
    for job in jobs:
        seen.add(job["external_id"])
        try:
            _, is_new, first_seen = store.upsert_job(job, existing, today)
            (new_jobs if is_new else active_jobs).append({**job, "first_seen": first_seen})
        except Exception as e:
            errors.append({"source": job["company"], "error": f"upsert: {e}"})

    closed = store.close_stale(seen, existing, today, grace_days=cfg.close_after_days)
    all_companies = {s["company"] for entries in cfg.sources.values() for s in entries}
    silent = sorted(all_companies - {j["company"] for j in jobs})

    log.info("new=%d active=%d closed=%d errors=%d", len(new_jobs), len(active_jobs), len(closed), len(errors))
    digest.send(f"Job digest · {len(new_jobs)} new · {now:%Y-%m-%d}", digest.render(new_jobs, active_jobs, closed, errors, silent, now))
    return 0


if __name__ == "__main__":
    sys.exit(main())
