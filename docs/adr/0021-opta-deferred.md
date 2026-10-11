# 21. Opta feeds: deferred to backlog

Status: Deferred — 2026-10-12

## Context
The author has access to Opta feeds (`omo.akamai.opta.net/competition.php`: F1 fixtures, F9 match details, F24 full event data with x/y coordinates, timestamps and qualifiers, F40 squads, F30 season stats). F24 would enable possession chains, expected threat (xT) and possession value (VAEP), which the scraped sources cannot.

## Decision
Opta is not used in the MVP. It stays in the backlog.

## If revisited
- Confirm first that the license permits use in a public portfolio project (repo, demo video, derived outputs).
- Default shape: an optional `OptaSource` behind the common source interface; the public default keeps working without Opta credentials.
- Credentials only in a gitignored `.env`; strip them from URLs before storing Raw Responses or logs (the feed puts the password in the query string); run `gitleaks` in pre-commit and CI.
