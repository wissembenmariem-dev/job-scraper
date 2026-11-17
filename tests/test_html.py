from bs4 import BeautifulSoup

from job_scraper.sources.html import parse_generic, parse_with_selectors

PAGE = """
<div class="job-card"><h3>Data Engineer</h3><a href="/jobs/42">Apply</a><span class="job-location">Brussels</span></div>
<div class="job-card"><h3>Platform Engineer</h3><a href="https://other.test/jobs/7">Apply</a></div>
<a href="/about">About us and our history</a>
"""


def test_selector_parser_resolves_links_and_locations():
    source = {"company": "Acme", "url": "https://acme.test/careers", "default_location": "Remote",
              "selectors": {"item": ".job-card", "title": "h3", "link": "a[href]", "location": ".job-location"}}
    jobs = parse_with_selectors(BeautifulSoup(PAGE, "lxml"), source)
    assert [(j["title"], j["url"], j["location"]) for j in jobs] == [
        ("Data Engineer", "https://acme.test/jobs/42", "Brussels"),
        ("Platform Engineer", "https://other.test/jobs/7", "Remote"),
    ]


def test_generic_parser_keeps_only_job_like_links():
    page = '<li><a href="/jobs/1">Senior Backend Engineer</a><span class="location">Ghent</span></li><a href="/blog/x">Our engineering blog post</a>'
    jobs = parse_generic(BeautifulSoup(page, "lxml"), {"company": "Acme", "url": "https://acme.test"})
    assert [(j["title"], j["location"]) for j in jobs] == [("Senior Backend Engineer", "Ghent")]
