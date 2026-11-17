from __future__ import annotations

import html
import logging
import os
from datetime import datetime
from typing import Any, Dict, List

import requests

log = logging.getLogger(__name__)

RESEND_URL = "https://api.resend.com/emails"
PALETTE = ["#4A90E2", "#50C878", "#E67E22", "#9B59B6", "#E74C3C", "#1ABC9C", "#F39C12"]


def _color(company: str) -> str:
    return PALETTE[sum(map(ord, company)) % len(PALETTE)]


def _row(job: Dict[str, Any], muted: bool = False) -> str:
    company = html.escape(job.get("company", ""))
    meta = " · ".join(x for x in (company, html.escape(job.get("seniority") or "")) if x)
    since = f" · open since {job['first_seen']}" if muted and job.get("first_seen") else ""
    bg = "#fafafa" if muted else "#fff"
    return (
        f'<tr><td style="padding:12px 16px;border-bottom:1px solid #eee;background:{bg};">'
        f'<div style="font-size:11px;text-transform:uppercase;letter-spacing:.4px;color:{_color(company)};font-weight:600;">{meta}{since}</div>'
        f'<div style="font-size:15px;font-weight:600;margin-top:3px;"><a href="{html.escape(job.get("url") or "#")}" style="color:#111;text-decoration:none;">{html.escape(job.get("title", ""))}</a></div>'
        f'<div style="font-size:12px;color:#777;margin-top:2px;">{html.escape(job.get("location") or "")}</div>'
        "</td></tr>"
    )


def _section(title: str, body: str) -> str:
    return (
        f'<tr><td style="padding:18px 32px 6px;font-size:13px;font-weight:700;color:#555;text-transform:uppercase;letter-spacing:.4px;">{title}</td></tr>'
        f'<tr><td><table width="100%" cellpadding="0" cellspacing="0">{body}</table></td></tr>'
    )


def render(new_jobs: List[Dict[str, Any]], active_jobs: List[Dict[str, Any]], closed: List[Dict[str, Any]],
           errors: List[Dict[str, Any]], silent_sources: List[str], generated_at: datetime) -> str:
    new_rows = "".join(_row(j) for j in new_jobs) or '<tr><td style="padding:16px 32px;color:#888;font-style:italic;">No new openings today.</td></tr>'
    active_rows = "".join(_row(j, muted=True) for j in sorted(active_jobs, key=lambda j: j.get("first_seen") or ""))
    footer = ""
    if silent_sources:
        footer += '<p style="font-size:12px;color:#888;">No matching openings: ' + ", ".join(map(html.escape, silent_sources)) + "</p>"
    if errors:
        items = "".join(f"<li>{html.escape(e['source'])}: {html.escape(e['error'])[:200]}</li>" for e in errors)
        footer += f'<div style="padding:12px 16px;background:#fff6e6;border-left:4px solid #f0ad4e;font-size:12px;"><strong>Failed sources</strong><ul>{items}</ul></div>'
    summary = f"<strong>{len(new_jobs)}</strong> new · <strong>{len(active_jobs)}</strong> active · <strong>{len(closed)}</strong> closed"
    return (
        '<!DOCTYPE html><html><head><meta charset="utf-8"></head>'
        "<body style=\"margin:0;background:#f4f5f7;font-family:-apple-system,'Segoe UI',Roboto,sans-serif;\">"
        '<table width="100%" cellpadding="0" cellspacing="0" style="padding:30px 0;"><tr><td align="center">'
        '<table width="640" cellpadding="0" cellspacing="0" style="background:#fff;border-radius:10px;overflow:hidden;">'
        f'<tr><td style="padding:28px 32px 16px;border-bottom:1px solid #eee;"><div style="font-size:24px;font-weight:700;">Job digest · {generated_at:%d %B %Y}</div>'
        f'<div style="font-size:13px;color:#666;margin-top:8px;">{summary}</div></td></tr>'
        + _section("New openings", new_rows)
        + (_section("Still open", active_rows) if active_rows else "")
        + f'<tr><td style="padding:16px 32px 24px;">{footer}<p style="font-size:11px;color:#999;">Generated {generated_at:%Y-%m-%d %H:%M %Z}</p></td></tr>'
        "</table></td></tr></table></body></html>"
    )


def send(subject: str, html_body: str) -> None:
    r = requests.post(
        RESEND_URL,
        json={"from": os.environ["EMAIL_FROM"], "to": [os.environ["EMAIL_TO"]], "subject": subject, "html": html_body},
        headers={"Authorization": f"Bearer {os.environ['RESEND_API_KEY']}"},
        timeout=20,
    )
    r.raise_for_status()
    log.info("Digest sent to %s", os.environ["EMAIL_TO"])
