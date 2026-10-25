# 32. The Reep register corroborates Identity Resolution

Status: Proposed — 2026-10-25. Refines ADR 6 (identity resolution).

## Context
Identity Resolution's rules (ADR 6, #47) link 539 of 577 Transfermarkt players and 865 of 874 Understat players to the Sofascore players that anchor Players. 18 Candidates stay pending for the LLM judge. Transfermarkt only has the current squads, so players who left the Premier League since 24/25 have no Transfermarkt link at all.

[Reep](https://reep.football) is a football identity register. It maps players, clubs, matches and competitions across 30+ providers, Sofascore, Transfermarkt and Understat among them. Its releases are CC0: free for any use, attribution optional. Each release is a set of Parquet files with a manifest that holds SHA-256 checksums and the release's own quality gates. Each bridge (`provider`, `namespace`, `external_id` to a Reep ID) carries a confidence and the rule that made it, and a redirects table maps merged Reep IDs to the survivors. The hosted API is paid beyond a 30-day evaluation; the downloads are not.

A spike on 2026-10-25 compared release `2026-10-25.1` with our links (details on #49):

- **Coverage:** 666 of our 1,094 Sofascore players (61 %), and 604 of the 874 who played (69 %). Most of Reep's Sofascore IDs come from Wikidata, which misses young and recent players.
- **Agreement:** 854 of the 855 links both sides have.
  - The one disagreement is Reep's: it maps Wolves' André to an Understat ID with no Premier League Appearance.
- **Additions:**
  - It confirms 8 of the 18 pending Candidates.
  - It has 273 Transfermarkt links and 26 Understat links for our players that our rules lack.
- **Release quality:** this release reports `gate_passed: false`, failing its "detected conflicts" and "lineup coverage" checks.

So Reep is accurate where it has a player, has gaps, and is sometimes wrong. That makes it good evidence, but not proof.

## Decision
- **A pinned Reep release is a reference input, not a scraped Source.**
  - The release tag is set in configuration.
  - A command downloads the release's player bridges and redirects into `data/reep/<tag>/` (outside version control) and verifies them against the manifest's checksums.
  - A failed checksum stops the load.
  - The manifest's gate result is recorded with the release, but it does not block: Reep only ever corroborates.
- **Loading.**
  - The Sofascore, Transfermarkt and Understat player bridges are loaded, with redirects resolved, into an Alembic-managed table (ADR 29) in a `reference` schema, keyed by release tag.
  - Only the pinned release is read. A new release is a configuration change, and its load is re-runnable.
- **Use in Identity Resolution.** After the rules and fuzzy scoring, before the LLM judge:
  - **Agreement accepts.** A pending Candidate whose Source Record Reep maps to the same Sofascore player is accepted, with `decided_by = reep:<tag>` and the bridge in its evidence.
  - **A Reep-only link is pending.** A Source Record with no Candidate that Reep maps to one of our Sofascore players becomes a pending Candidate with method `reep_bridge`, for the judge or a reviewer. It is never accepted on Reep alone.
  - **Disagreement is flagged, never applied.** When an accepted link's Source Record maps elsewhere in Reep, the run lists it. The link stays.
- **Unchanged:**
  - Sofascore anchors Players.
  - Our rules decide first.
  - Accepted links and Player IDs never change because of Reep.

## Consequences
- **About 10 Candidates are left for the LLM judge,** instead of 18.
- **About 300 extra pending Candidates** for players our sources cannot link, mostly Transfermarkt players who left the Premier League. They need the judge or a reviewer before they count.
- **A standing cross-check:** each release re-measures how far Reep and our rules agree.
- **New pinned dependency:** a Parquet reader (`duckdb` or `pyarrow`) in the worker, plus about 400 MB per release download, kept under `data/`.
- **Reep's IDs for clubs, competitions and matches stay unused for now.** They could later replace the hand-made club seed (#46). That needs its own decision.
- **Rejected alternatives:**
  - **Reep as the primary mapping.** Its coverage of our players is 61–69 %, and it has errors.
  - **The hosted API.** It is paid for production use, and it adds a network dependency at resolution time.
