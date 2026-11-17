# Job Scraper

Configurable job board aggregator. It collects openings from company career sites, filters them by keywords and location, keeps a lifecycle per posting in Notion and emails a daily digest.

## How it works

```
sources.yaml ──► adapters ──► filters ──► Notion ──► email digest
                 Workday       keywords    New → Active → Closed
                 Oracle HCM    locations
                 HTML          seniority, category, stable IDs
```

- **Adapters**: Workday CXS API, Oracle HCM Candidate Experience API, and HTML pages either with CSS selectors or with a generic heuristic parser.
- **Filtering**: accent and case insensitive keyword, exclusion and location matching; seniority and category classification; deduplication through stable external IDs.
- **State**: Notion is the single source of truth. Each run creates new postings, refreshes the ones still online and closes the ones not seen for `close_after_days`.
- **Digest**: HTML email through Resend with new openings, still-open roles, silent sources and failures.

## Configuration

Copy `sources.example.yaml` to `sources.yaml` and declare your targets:

```yaml
filters:
  keywords: [software engineer, data engineer]
  exclude_keywords: [intern]
  locations: [brussels, remote]

sources:
  workday:
    - {company: Example Corp, host: examplecorp.wd3.myworkdayjobs.com, tenant: examplecorp, site: External}
  html:
    - company: Acme Software
      url: https://careers.example.com/jobs
      selectors: {item: .job-card, title: h3, link: "a[href]", location: .job-location}
```

Environment variables (see `.env.example`):

| Variable | Purpose |
|---|---|
| `NOTION_TOKEN`, `NOTION_DATABASE_ID` | Target Notion database |
| `RESEND_API_KEY`, `EMAIL_FROM`, `EMAIL_TO` | Digest delivery |
| `SOURCES_FILE` | Path to the sources file, `sources.yaml` by default |

The Notion database needs these properties: `Title` (title), `Company`, `Status`, `Source`, `Category`, `Seniority` (select), `Location`, `External ID` (text), `URL` (url), `First Seen`, `Last Seen`, `Posted Date`, `Closed Date` (date).

## Run

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env && cp sources.example.yaml sources.yaml
pytest
python -m job_scraper
```

`.github/workflows/scrape.yml` runs the scraper daily on GitHub Actions; `ci.yml` runs the test suite on every push.

## License

Copyright (c) 2026 Wissem Ben Mariem. All rights reserved. See [LICENSE](LICENSE).
