# 34. Canonical IDs are ours, not any source's

Status: Proposed — 2026-10-25. Supersedes ADR 33. Amends ADR 32 (which source mints Players) and ADR 31 (the identity step's order).

## Context
Every source we use may go away: a site can close, change its API, or block scraping for good. Sofascore did for six days in October 2026 (ADR 30). Reep is a third-party register and can stop publishing too. So the platform's canonical entities must not take their identity from any one of them.

Today, three things do:

- **Players.** IDs are ours (`identity.players`), but a Player is only ever created from a Sofascore player: "Sofascore anchors Players" (ADR 32). Without Sofascore, no new Player could exist.
- **Clubs.** ADR 33 made Reep's team ID the Club ID.
- **Matches.** The Match ID is built from the Club IDs, so it inherits that dependency.

## Decision
- **Canonical IDs are minted by us and kept in the Alembic-managed `identity` schema** (ADR 31). They never change once minted, and are never a source's or Reep's ID. A source's ID is only ever a link to one of ours: an Identity Candidate.
- **Players:** `identity.players.player_id`, a sequence, as today.
- **Clubs:** `identity.clubs.club_id`, a readable slug minted once from the club's name when it is first seen, such as `arsenal` or `wolverhampton-wanderers`.
  - ASCII, lower case, hyphenated.
  - A slug already taken gets a disambiguating suffix (`-2`).
  - It never changes, even if the club is renamed. The display name is a separate, updatable column.
- **Competitions:** `identity.competitions.competition_id`, a short slug we choose, such as `premier-league`. It is minted by hand, since we add a competition deliberately.
- **Seasons:** the start year (glossary), already source-independent.
- **Matches:** `<competition>:<season>:<home club>:<away club>`, such as `premier-league:2025:arsenal:chelsea`.
  - It is built only from our own IDs, so it needs no table of its own.
  - In a league season the pair occurs once.
  - A competition where the same home and away pair can meet twice in a season (a cup replay) needs its own rule before it is added.
- **Mapping into our IDs.** For Clubs as for Players, the order is the one decided in ADR 32:
  1. **Reep:** a source record whose Reep entity already has a link from another source joins that canonical entity.
  2. **Rules:** deterministic rules, then fuzzy scoring.
  3. **The LLM judge and review.**
  4. **Minting:** a source record that none of these links mints a new canonical entity.

  Reep's own IDs are evidence, never our IDs.
- **Any source can mint.** Sources are processed in a preference order, today Sofascore, then Transfermarkt, then Understat, because the earlier ones carry more identifying data (birth dates, full lineups). That order is a preference, not a dependency: if a source disappears, the next one mints.
- **Order inside the identity step** (ADR 31's step 2): Clubs, then Matches (derived from Club links), then Players, whose co-appearance rule needs Matches. Matches are derived inside the step from staging plus Club links, not from a dbt mart. The marts then read the `identity` schema (step 3).
- **Kept from ADR 33:**
  - `load-reep` also loads team bridges (Sofascore `team`, Understat `team`, Transfermarkt `verein`).
  - The hand-made club seed stays deleted.

## Consequences
- **Losing a source keeps every ID.** Its links stop growing, and another source mints new entities.
- **IDs are readable** (`premier-league:2025:arsenal:chelsea`, `arsenal`) and stable for as long as our Club IDs are, which is forever by rule.
- **The `identity` schema grows:** a `clubs` and a `competitions` table, and Identity Candidates that also link Clubs. That is state dbt cannot rebuild, so it is backed up with the rest of `identity`.
- **A wrongly minted duplicate Club**, for example when Reep and the rules both miss a match, is fixed by a review that links the source record to the existing Club. The duplicate is retired, and a redirect from it to the survivor keeps any cited ID working. Players get the same treatment.
- **ADR 33 is superseded.** Its decision that the Club ID is Reep's is replaced; loading team bridges and deleting the seed are kept here.
- **ADR 32 is amended:**
  - "Sofascore anchors Players" becomes "any source can mint a Player, Sofascore first by preference".
  - Reep stays the first mapping layer, for Clubs as well.
- **Rejected:**
  - **Sofascore's IDs** (events, teams) as canonical IDs. Readable enough, but they tie the platform to Sofascore.
  - **Reep's IDs** as canonical IDs. They are source-independent of the scraped sites, but tie the platform to Reep.
  - **Opaque surrogate IDs for Clubs and Matches.** They are stable, but a slug serves the agent's citations and people better at no extra cost.
