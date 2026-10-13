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
A stealth browser that passes the Turnstile, followed by `fetch()` calls made from inside its page. The same token, sent from `curl_cffi` straight after, is still challenged: requests have to come from the browser that solved the captcha.

Every option was run the same way, one at a time and 20–25 seconds apart, each with a fresh profile:

1. load `captcha.html`;
2. wait up to 45 seconds for the redirect to `/`;
3. call `/event/{id}`, `/event/{id}/lineups` and `/unique-tournament/17/seasons` from inside the page.

An option passes when all three answer 200. A solve issues a `sofa_captcha` cookie whose `exp` is 60 minutes ahead. In-page calls answer 200 with or without the `x-captcha` and `x-requested-with` headers.

**On the developer's Mac (macOS, arm64):**

| Option | Headless | Headed |
|---|---|---|
| **camoufox 0.5.8** (anti-detect Firefox), no solver | **5/5** (4–29 s) | 1/1 |
| seleniumbase 4.56 UC mode | 3/4 (16–20 s) | 1/1 |
| Scrapling 0.4.15 `StealthySession(solve_cloudflare=True)` on patchright Chromium (#206, tunjayoff) | 1/4 | 1/1 |
| patchright 1.63, no solver | 0/1 | 1/1 (14 s) |
| zendriver 0.17 / nodriver 0.50 with `verify_cf()` | 0/1 each | 1/1 each |
| Playwright 1.62, no solver | 0/1 | — |
| Botasaurus 4.0 (`bypass_cloudflare=True`) | 0/1 ("Cloudflare has detected us") | 0/1 |
| Installed Chrome with Scrapling (`real_chrome=True`) | 0/1 | 1/1 (16 s) |

With a headed browser, the Turnstile passes on its own for almost every option. Headless, only camoufox passed reliably, and it never needed a checkbox click.

**Soak.** One camoufox headless session made 450 in-page API calls over 15 minutes at 0.5 requests per second: season lists, event lists, events, lineups, shotmaps and average positions. All 450 answered 200, and no challenge came back.

**In a Linux container (Debian bookworm, arm64, Docker Desktop):**
- camoufox headless failed 2/2.
- Scrapling on patchright Chromium failed 1/1, although tunjayoff reports this setup working in its image.
- seleniumbase's UC driver does not start on Linux arm64.
- Runs under a virtual display (camoufox `headless="virtual"`, with and without `geoip`) failed before reaching Sofascore. Their cause was not diagnosed, so Linux with a virtual display remains untested.

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
- **A Browser Bridge is the Sofascore backend.**
  - It is one long-lived **camoufox** session, headless, with a persistent profile under `data/`. It runs **on the developer's Mac**.
  - It replaces `curl_cffi` impersonation for Sofascore only.
  - It sits behind the common source interface as the `httpx` transport backend that `SourceInterface` already accepts (`backend=`). The rate limit, circuit breaker, Raw Response recording and Fetch Attempts therefore apply unchanged, and the activities and parsers do not change.
- **The ingestion worker runs on the host.** It starts with `uv run`, and the compose `worker` service is removed. Temporal, Postgres and the rest of the stack stay in compose. ADR 22 already keeps ingestion on the developer's machine. A worker on the host, rather than a separate bridge process, keeps everything in one process with nothing new to deploy. Transfermarkt runs in the same worker unchanged.
- **Every Sofascore request is an in-page `fetch()`** from a `www.sofascore.com` page that has a Captcha Token. The fetch uses `cache: "no-store"`. The result goes back through the transport as an ordinary `httpx.Response`, so it is stored as a Raw Response like any other answer.
- **Solving.** camoufox passes the Turnstile without a solver: the bridge loads `captcha.html` and waits for the redirect.
  - The bridge solves on launch, when the API answers `challenge` or `jwt:*`, and about 15 minutes before the token's `exp`.
  - Before a re-solve it clears `sofa_captcha`, because `captcha.html` redirects without issuing a new token while a cookie is present.
  - After a failed solve it backs off 180, 180, 360, then 600 seconds, and it loads `captcha.html` at most 8 times in any hour (#206's limits).
  - While a solve is backing off, a request answers `ChallengeError` without being sent, so a backfill stops as PR #35 does today.
- **Fallback.** If camoufox stops passing, seleniumbase UC mode on the host is next (3/4 headless). The last resort is a headed browser, which passes with almost every option.
- **Recycling.** The bridge restarts its browser, keeping the same profile, at a memory ceiling or a maximum age, and only while the token has at least 10 minutes left.
- **Unchanged:**
  - Sofascore's rate limit stays at 0.5 requests per second (ADR 4).
  - No scraped data is committed or redistributed.
  - Transfermarkt and Understat do not change.
- **Amendments:**
  - ADR 4 gains an exception: for Sofascore, the platform passes the source's human-verification challenge with an anti-detect browser, at polite rates.
  - ADR 14's "Playwright as a fallback for sources that require JavaScript" becomes "an anti-detect browser (camoufox) for Sofascore, whose API requires a captcha-bound session".

## Consequences
- **Sofascore stays the primary source of stats and spatial data (ADR 3)**, at the cost of one Firefox process on the host. camoufox's browser is downloaded once with `camoufox fetch`, and memory grows by about 0.5–2 GiB.
- **Ingestion only runs where the bridge runs.** The worker leaves compose for the host, so `docker compose up` alone no longer ingests. Moving ingestion to a server (ADR 22) would need a browser that passes on Linux, which is unverified today.
- **New pinned dependency:** `camoufox`, plus the Firefox build it fetches. A change to Turnstile or to camoufox's fingerprints can stop it passing without warning. The failure is loud (`ChallengeError`). The fix is a version bump or the fallback, and #206's pinned-version tests are the model for catching it.
- **Throughput:**
  - Requests are serialised through one page. 0.5 requests per second is well below what the page can do, so the rate limit, not the bridge, sets the pace.
  - A solve costs 5–30 seconds about once an hour.
  - A challenge wall that solving cannot pass stops ingestion through `ChallengeError` (PR #35) instead of burning attempts.
- **Terms of use.** Solving a site's bot check automatically very likely breaches Sofascore's terms of use, more directly than impersonating a browser's TLS, even though camoufox passes without clicking the checkbox. That is the main cost of this decision and the reason it needs explicit acceptance. If it is not accepted, the alternatives are:
  - ingest Sofascore only while the challenge happens to lift, as on 2026-10-13 16:26–16:46 UTC;
  - drop Sofascore and take spatial data from another source under a new ADR 3 decision.
- **Tests.** Tests keep stubbing the transport. The bridge's own logic (solve backoff, refresh timing, the 8-loads-per-hour cap, held-back requests) is unit-tested with a fake page, as #206 did.

## Open questions for the implementation
1. Does a camoufox session last across token expiry? The soak ran for 15 minutes, and tokens last 60. A soak of several hours at 0.5 requests per second answers this, and also whether volume brings the challenge back, as it did after about 1,300 tokenless requests.
2. How often does a solve fail over a day? #206's soak saw three failed refreshes in a row and one 24-minute outage.
3. Does any browser pass in Linux under a virtual display? Only this would move ingestion off the host. It is not needed while ADR 22 keeps ingestion local.
