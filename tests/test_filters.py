from datetime import date

from job_scraper.config import Filters
from job_scraper.filters import classify_category, classify_seniority, normalize_and_filter
from job_scraper.sources.workday import parse_posted_on

FILTERS = Filters(keywords=["engineer"], exclude_keywords=["intern"], locations=["brussels", "remote"])
CATEGORIES = {"Engineering": ["engineer"], "Data": ["data"]}


def job(title, location="Brussels, Belgium", url="https://x.test/1", company="Acme"):
    return {"company": company, "title": title, "location": location, "url": url}


def test_keeps_matching_job_and_enriches_it():
    [out] = normalize_and_filter([job("Senior Backend Engineer")], FILTERS, CATEGORIES)
    assert out["seniority"] == "Senior"
    assert out["category"] == "Engineering"
    assert out["external_id"].startswith("Acme::")


def test_rejects_wrong_location_excluded_keyword_and_duplicates():
    jobs = [
        job("Backend Engineer", location="Paris"),
        job("Engineer Intern"),
        job("Data Engineer", url="https://x.test/2"),
        job("Data Engineer", url="https://x.test/2"),
    ]
    out = normalize_and_filter(jobs, FILTERS, CATEGORIES)
    assert [j["title"] for j in out] == ["Data Engineer"]


def test_location_matching_ignores_accents_and_case():
    out = normalize_and_filter([job("Engineer", location="BRÜSSELS")], Filters(locations=["brussels"]), {})
    assert out


def test_seniority_and_category_fallbacks():
    assert classify_seniority("Engineering Manager") == "Manager"
    assert classify_seniority("Engineer") is None
    assert classify_category("Accountant", CATEGORIES) == "Other"


def test_workday_relative_dates():
    today = date(2026, 1, 31)
    assert parse_posted_on("Posted Today", today) == "2026-01-31"
    assert parse_posted_on("Posted Yesterday", today) == "2026-01-30"
    assert parse_posted_on("Posted 30+ Days Ago", today) == "2026-01-01"
    assert parse_posted_on(None, today) is None
