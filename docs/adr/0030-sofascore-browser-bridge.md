# 30. Sofascore through a browser bridge that solves its captcha

Status: Proposed — 2026-10-13. Would amend ADR 4 (scraping posture) and ADR 14 (access method) for Sofascore only.

## Context

### The challenge
ADR 3 and ADR 14 rest on a probe from 2026-10-11: Sofascore's `www.sofascore.com/api/v1/*` answered 200 to `curl_cffi` with Chrome impersonation. That no longer holds. Sofascore now answers API requests with `403 {"error": {"code": 403, "reason": "challenge"}}` from its own Varnish edge, and this is not a Cloudflare TLS block. Public reports date the challenge for plain clients to about June 2026 (ScraperFC #93). On our IP it has come and gone:

- 2026-10-13, 16:26–16:46 UTC: the #21 backfill fetched about 1,300 requests at about 0.9 requests per second. Then the challenge started.
- 19:37 UTC, after three idle hours: the first request was challenged. Every request since has been challenged too.
- 20:10 UTC: `curl_cffi` as `chrome` and as `safari`, a homepage warm-up with `Referer`/`Origin`, plain `curl` and `api.sofascore.com` were all challenged.

The homepage itself serves Sofascore's captcha page (`/captcha.html?redirectUrl=…`). It renders a Cloudflare Turnstile widget (sitekey `0x4AAAAAADcoqB6O4KpaoADv`). The solution is POSTed to `/api/v1/token/captcha` (`{"response": <turnstile token>, "provider": "turnstile"}`), which returns a JWT. The web app stores that JWT in localStorage `sofa.captcha.token` and in the `sofa_captcha` cookie, and sends it as the `X-Captcha` request header.

### What does not get past it (probed 2026-10-13)
- **A token solved by hand, replayed from another client.** The JWT is HS256 with the claims `exp`, `ip` and `f`. `exp` is about 50–60 minutes after the solve. `ip` is the solver's public IP, which matched the worker's. `f` is a 6-hex-digit hash bound to the solving browser. The token was rejected with `403 challenge` when sent from a client other than the browser that solved it:
  - `curl_cffi` as `chrome`, `chrome146`, `chrome150` and `safari`, sending it as `X-Captcha`
  - the same, sending it as the `sofa_captcha` cookie
  - the same, adding the browser's exact User-Agent
  - plain `curl`
- **The `x-requested-with` header.** The web app sends `x-requested-with: sha256(str(unix_time // 1800))[:6]`, a value that rotates every 30 minutes. Sending it, with or without a token, was challenged too. It is not the token's `f` claim.
- **The installed Chrome, headless.** Scrapling's stealth session with `real_chrome=True`, headless, reported the Turnstile solved. The page never left `captcha.html`, no token was issued, and in-page API calls were challenged. #32 recorded the same for plain Playwright, headless and headed. Stealth patches matter more than headed or headless.

### What does get past it (probed 2026-10-13)
A stealth browser that solves the Turnstile itself. Two setups passed, both with Scrapling 0.4.15 `StealthySession(solve_cloudflare=True)` and a scratch profile, on the developer's Mac:

- **Headless, with patchright's bundled Chromium** (Chrome for Testing 153, `executable_path`): solved in 35 seconds.
- **Headed, with the installed Chrome** (`real_chrome=True`, `headless=False`): solved in 16 seconds.

In both runs:

1. It loaded `captcha.html`.
2. Scrapling clicked the Turnstile checkbox.
3. The page redirected to `/` within 16 seconds, with a `sofa_captcha` cookie (`exp` 60 minutes ahead).
4. `fetch()` calls made from inside that page answered **200** for `/event/{id}`, `/event/{id}/lineups` and `/unique-tournament/17/seasons`, with or without the `x-captcha` and `x-requested-with` headers.

The same token, sent from `curl_cffi` straight after, was still challenged. Requests have to come from the browser that solved the captcha.

### Prior art
- **tunjayoff/sofascore_scraper PR #206** ("Turnstile and request-layer hardening", closed unmerged when its owner ended the project). It ran a long-lived "bridge" browser (Scrapling `StealthySession` on patchright Chromium, persistent profile) and sent every API request as an in-page `fetch()`. From its soak runs:
  - Tokens last 3,600 seconds. After expiry the API answers a `jwt:time-out-of-bounds` 403.
  - It refreshed tokens 15 minutes before `exp`, with at most 3 refresh loads per token.
  - After a failed solve it waited 180, 180, 360, then 600 seconds.
  - It loaded `captcha.html` at most 8 times per hour, and gave each solve 15 seconds to redirect (passing solves redirected in 3.4–4.5 seconds).
  - It recycled the browser at 2 GiB of memory or after 6 hours, only while the token had at least 10 minutes left.
  - It turned the browser HTTP cache off for stateful responses, so a cached response cannot keep showing a finished match as in progress.
  - It cleared the cookie before a re-solve, because `captcha.html` redirects without issuing a new token while a cookie is present.
- **tunjayoff/sofascore_scraper `main`.** Its released `BrowserBridge` is headless patchright Chromium through Scrapling `StealthySession`. Its changelog says it "passes the Cloudflare Turnstile challenge on its own" and "runs headless on a desktop and on a display-less server alike". Its Docker image installs it with `patchright install --with-deps --no-shell chromium`, with no Xvfb. After a challenge, it sends requests straight to the browser for 10 minutes ("browser-first"). Its status notes record every plain `curl` request challenged on 29 September 2026.
- **Botasaurus**, an anti-detect Chromium wrapper.
  - Sharone-12/sofascore-scraper (October 2026) uses it headless and fetches the API URLs as page navigations. It reports that Playwright with stealth patches failed while the token was being issued, and Botasaurus passed "cleanly: headless, no manual click".
  - ScraperFC PR #94 (open since June 2026, unmerged) warms a Botasaurus session on the homepage, then issues in-page XHRs. ScraperFC's own Sofascore scraper (issue #93) has been broken since June.
- **Crawlora** sells a hosted Sofascore API. ADR 14 rules out paid scraping APIs.
- **probberechts/soccerdata.**
  - #835 (May 2025) only gets past TLS fingerprinting, with `tls-requests`, which is what our `curl_cffi` already does.
  - #955 (July 2026) added a seleniumbase captcha solver (`uc_gui_handle_captcha`), but only for its Selenium readers (WhoScored, FBref). It refuses to run headless.
  - Its Sofascore reader is still plain HTTP, so it has nothing for this challenge.
- **#34 / PR #35.** A challenge now raises `ChallengeError`. It is not retried, and a backfill stops at the first one instead of spending every Match's attempts against it.

## Decision (proposed)
- **A Browser Bridge is the Sofascore backend.** It is one long-lived headless stealth browser per worker: Scrapling `StealthySession` on patchright's bundled Chromium, `solve_cloudflare=True`, a persistent profile under `data/`. It does not use the installed Chrome, which fails headless. It replaces `curl_cffi` impersonation for Sofascore only. It sits behind the common source interface as the `httpx` transport backend that `SourceInterface` already accepts (`backend=`). The rate limit, circuit breaker, Raw Response recording and Fetch Attempts therefore apply unchanged, and the activities and parsers do not change.
- **Every Sofascore request is an in-page `fetch()`** from a `www.sofascore.com` page that has a Captcha Token. The fetch uses `cache: "no-store"` and sends the web app's `x-captcha` and `x-requested-with` headers. The result goes back through the transport as an ordinary `httpx.Response`, so it is stored as a Raw Response like any other answer.
- **Solving:**
  - The bridge solves on launch, when the API answers `challenge` or `jwt:*`, and in the background about 15 minutes before the token's `exp`.
  - Before a re-solve it clears `sofa_captcha`.
  - After a failed solve it backs off 180, 180, 360, then 600 seconds, and it loads `captcha.html` at most 8 times in any hour.
  - While a solve is backing off, a request answers `ChallengeError` without being sent, so a backfill stops as PR #35 does today.
- **Where it runs.** The bridge runs in the worker container, headless, with no display. tunjayoff's Docker image does the same in production. The implementation first verifies that Turnstile passes in Linux Chromium in our container. If it does not, there are two fallbacks:
  - a headed browser under Xvfb;
  - a bridge on the host, which the worker reaches over a local HTTP port. ADR 22 keeps ingestion on the developer's machine, so this is available.
- **Recycling.** The bridge restarts its browser, keeping the same profile, at a memory ceiling or a maximum age, and only while the token has at least 10 minutes left.
- **Unchanged:**
  - Sofascore's rate limit stays at 0.5 requests per second (ADR 4).
  - No scraped data is committed or redistributed.
  - Transfermarkt and Understat do not change.
- **Amendments:**
  - ADR 4 gains an exception: for Sofascore, the platform solves the source's human-verification challenge automatically, at polite rates.
  - ADR 14's "Playwright as a fallback for sources that require JavaScript" becomes "a headless stealth browser for Sofascore, whose API requires a captcha-bound session".

## Consequences
- **Sofascore stays the primary source of stats and spatial data (ADR 3)**, at the cost of a browser per worker. The worker image grows by a Chromium build (about 190 MB) and its system libraries. Memory grows by about 0.5–2 GiB.
- **New pinned dependencies:** `scrapling[fetchers]` and `patchright`. Turnstile changes break the solver without warning. The fix is a Scrapling bump, and #206's pinned-version tests are the model for catching it.
- **Throughput:**
  - Requests are serialised through one page. 0.5 requests per second is well below what the page can do, so the rate limit, not the bridge, sets the pace.
  - A solve costs 5–20 seconds about once an hour.
  - A challenge wall that solving cannot pass stops ingestion through `ChallengeError` (PR #35) instead of burning attempts.
- **Terms of use.** Solving a site's bot check automatically very likely breaches Sofascore's terms of use, more directly than impersonating a browser's TLS. That is the main cost of this decision and the reason it needs explicit acceptance. If it is not accepted, the alternatives are:
  - ingest Sofascore only while the challenge happens to lift, as on 2026-10-13 16:26–16:46 UTC;
  - drop Sofascore and take spatial data from another source under a new ADR 3 decision.
- **Tests.** Tests keep stubbing the transport. The bridge's own logic (solve backoff, refresh timing, the 8-loads-per-hour cap, held-back requests) is unit-tested with a fake page, as #206 did.

## Open questions for the implementation
1. Does Turnstile pass headless in Linux Chromium in the worker container? It was probed only on macOS. tunjayoff reports that it passes in its Docker image.
2. Does the challenge come back with a valid token after enough volume, as it did after about 1,300 tokenless requests? A soak at 0.5 requests per second for several hours answers it.
3. How often does a solve fail over a day? #206's soak saw three failed refreshes in a row and one 24-minute outage.
