# 3. Live-only data sources: Transfermarkt, Sofascore, Understat

Status: Accepted — 2026-10-11

## Context
Requirement: only sources that stay current. StatsBomb Open Data was rejected — it is static and contains no current league seasons. FBref lost Opta advanced data in January 2026. API-Football is official but its player data has no coordinates. WhoScored has full Opta events but the heaviest anti-bot protection and an explicit terms-of-service problem.

Probed on 2026-10-11:
- Sofascore `www.sofascore.com/api/v1/*` returns 200 with browser TLS impersonation (`curl_cffi`, `impersonate="chrome"`); `api.sofascore.com` and plain curl return 403.
- Sofascore per-player match data: 49 statistics (incl. xG, xA, xGOT, progressive carries, distance/sprint/top-speed physical metrics, rating), heatmap points, shotmap, average positions, birth date, and a rating breakdown with located passes (start/end), dribbles, ball carries and defensive actions.
- Understat returns 200 to plain HTTP.

## Decision
MVP sources: Transfermarkt (via `transfermarkt-api`), Sofascore (primary stats and spatial data), Understat (independent second xG signal). WhoScored may be added later under its own ADR.

## Consequences
Every source is scraped, so ingestion must be resilient by design (see ADR 4). Sofascore provides birth dates, which simplifies identity resolution. Two xG providers allow cross-checking.
