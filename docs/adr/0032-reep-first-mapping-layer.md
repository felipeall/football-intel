# 32. The Reep register is the first mapping layer of Identity Resolution

Status: Accepted — 2026-10-25. Refines ADR 6 (identity resolution).

## Context
Identity Resolution (ADR 6, #47) links Transfermarkt and Understat players to the Sofascore players that anchor Players, with deterministic rules, fuzzy scoring, an LLM judge and human review. Its rules work on the data we have ingested.

[Reep](https://reep.football) is a curated football identity register. It maps players, clubs, matches and competitions across 30+ providers, Sofascore, Transfermarkt and Understat among them. Its releases are CC0: free for any use, attribution optional. A release is a set of Parquet files with a manifest that holds SHA-256 checksums and the release's own quality gates. A bridge maps a provider's ID (`provider`, `namespace`, `external_id`) to a Reep ID. Merged Reep IDs redirect to the survivor. The hosted API is paid beyond a 30-day evaluation; the downloads are not.

A spike on 2026-10-25 compared release `2026-10-25.1` with #47's links (details on #49):

- **Coverage:** 666 of our 1,094 Sofascore players (61 %), and 604 of the 874 who played (69 %). Most of Reep's Sofascore IDs come from Wikidata, which covers established players better than young ones. Coverage grows as we ingest more seasons and leagues.
- **Agreement:** 854 of the 855 links both sides have. The one disagreement is Reep's: it maps Wolves' André to an Understat ID with no Premier League Appearance.
- **Release quality:**
  - this release reports `gate_passed: false`, failing its "detected conflicts" and "lineup coverage" checks;
  - 99.6 % of player bridges have confidence 1.0, so confidence does not separate good bridges from bad ones.

A review of an earlier draft (on #58) proposed using Reep only as evidence for the LLM judge. We chose the simpler, curated-first design below, and accept Reep's rare errors for now.

## Decision
- **Reep decides first.**
  - For every Source Record we hold, Reep's bridge to one of our Sofascore players becomes an accepted Identity Candidate, with method `reep_bridge`, confidence 1.0 and `decided_by = reep:<release tag>`.
  - The bridge's `rule_id` and `route_scope` are kept as evidence.
  - Both IDs must be ones we hold: the Sofascore player in `stg_sofascore__players`, and the Transfermarkt or Understat player in its staging model.
- **Where Reep has no mapping, our rules decide,** as in ADR 6: deterministic rules, fuzzy scoring, the LLM judge and human review. They only see Source Records that Reep did not link. So the order is Reep, then rules, then fuzzy scoring, then the judge, then review.
- **A pinned release.**
  - The release tag is set in configuration.
  - A command downloads the release's bridges, redirects and manifest into `data/reep/<tag>/`, outside version control, and verifies each file against the manifest's checksums.
  - A failed checksum stops the load.
  - The manifest's gate result is recorded, but does not block the load.
- **Loading.**
  - Bridges are loaded with redirects resolved, into an Alembic-managed table (ADR 29) in a `reference` schema, keyed by release tag.
  - The table holds only persons that Reep maps to a Sofascore player, with their Sofascore, Transfermarkt and Understat IDs: about 28k rows per release.
  - The worker reads that table; it never reads the Parquet files.
- **Reep IDs for players we have not ingested are not Candidates.** A link needs a Source Record we hold.
- **Upgrades.**
  - A new release links Source Records that have no Candidate yet.
  - It never changes an existing Candidate: a Source Record is proposed once (#47). Player IDs and accepted links stay stable.
  - **The one exception:** a Source Record whose only Candidates are rejected `reep_bridge` ones is open to our rules again, so rejecting a wrong Reep link lets the rules relink it.
- **Unchanged:**
  - Sofascore anchors Players.
  - A Player has at most one link per source.

## Proposed, not implemented: our data can veto Reep
Before accepting a Reep bridge, check that our own data does not contradict it:

- **Transfermarkt:** the two birth dates match within one day (sources disagree by a day, as for El Hadji Malick Diouf).
- **Understat:** the two players appeared together in at least one Match for the same Club.

A bridge that fails would become a pending Candidate, listed as a disagreement for the judge or a reviewer, instead of an accepted link. The same check would flag bridges that a new release changes.

This would catch errors like the André bridge in cases where we hold both records. It is left out for simplicity, and can be added without changing this decision's order.

## Consequences
- **Fewer cases for our own matching:** on today's data, Reep links about 855 Source Records, and our rules handle about 550 more where Reep has no mapping.
- **Reep's errors become our errors.** In the spike that was 1 in 855. Such a link is fixed by rejecting its Candidate. Our rules then link the Source Record on the next run.
- **New pinned dependency:** a Parquet reader in the loader (`duckdb` or `pyarrow`), plus about 400 MB per release download under `data/`.
- **Reep data stays local.** It is CC0, but derived from providers' data, so it stays under `data/` and in the database, and is not redistributed (ADR 4).
- **Out of scope:** Reep's IDs for clubs, competitions and matches. They could replace the hand-made club seed (#46), and need their own decision.
- **Rejected:**
  - **Reep only as evidence for the LLM judge.** Safer, but it leaves the curated mapping unused for the bulk of links.
  - **The hosted API.** It is paid for production use, and adds a network dependency at resolution time.
