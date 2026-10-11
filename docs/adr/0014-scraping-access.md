# 14. Scraping access method

Status: Accepted — 2026-10-11

## Decision
HTTP via `curl_cffi` with browser impersonation from the developer's own IP; Playwright as a fallback for sources that require JavaScript. Proxy support exists as optional per-source configuration, not a dependency. No paid scraping APIs.
