# 33. The Reep register maps Clubs; the club seed goes

Status: Superseded by ADR 34 — 2026-10-25. Extended ADR 32 (Reep, first for players) to Clubs.

## Context
Canonical Clubs (#46) come from a hand-made dbt seed, `club_source_ids.csv`: 25 rows, each mapping a Club to its Sofascore, Understat and Transfermarkt IDs. Every Club new to the league needs a row by hand, or `dbt build` fails its not-null test. ADR 32 made the pinned Reep release the first mapping layer for players, and left club IDs out of scope.

Checked against release `2026-10-25.1`:

- **All 25 seed rows agree with Reep.** The three IDs map to one Reep team each: Arsenal's Sofascore 42, Understat 83 and Transfermarkt 11 all map to `rt13f99514be4cfd`.
- **Coverage:** Reep has 11,171 teams with a Sofascore bridge, 202 with an Understat bridge (Understat covers six leagues), and Transfermarkt teams in the `verein` namespace.
- **Uniqueness:** no Sofascore team ID maps to more than one Reep team.

## Decision
- **The Club ID is Reep's team ID** (`rt…`), stable under Reep's ID policy and its redirects. A Match ID becomes `<season>:<home Reep ID>:<away Reep ID>`. Nothing cites Club or Match IDs yet, so the change costs nothing now.
- **`load-reep` also loads team bridges** for Sofascore (`team`), Understat (`team`) and Transfermarkt (`verein`), limited to teams with a Sofascore bridge and with redirects resolved. They go into a `reference` table next to the player bridges, keyed by release.
- **dbt reads them** as a source and builds `marts.clubs`. dbt never writes to `reference` (ADR 31).
  - The display name is Sofascore's team name, from staging.
  - A Club is every Reep team mapped from a Sofascore team in our stored Matches.
- **The seed is deleted.** A Club without a Reep mapping fails `dbt build`'s not-null test on the Match's Club. The fix is a newer Reep release, not a CSV edit.

## Consequences
- **A newly promoted Club needs no manual step,** as long as Reep maps it. Reep has three sources' bridges for every Premier League club of the last three seasons.
- **Match and Club IDs are less readable** (`2025:rt13f…:rt8a1…` against `2025:arsenal:chelsea`). The marts carry names next to IDs.
- **Clubs depend on the pinned Reep release,** like players. `dbt build` needs `load-reep` to have run once.
- **Rejected:**
  - **Keeping the seed as a fallback.** Two sources for one mapping drift apart, and Reep covers every club we use.
  - **Our own slugs as IDs.** They would need a name source and a uniqueness rule we would have to maintain.
