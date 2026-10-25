# 34. Canonical IDs are ours, not any source's

Status: Accepted — 2026-10-25. Supersedes ADR 33. Amends ADR 31 (Transform Run steps) and ADR 32 (Reep load filters, Player anchor).

## Context
Every source we use may go away: a site can close, change its API, or block scraping for good. Sofascore did for six days in October 2026 (ADR 30). Reep is a third-party register and can stop publishing too. So the platform's canonical entities must not take their identity from any one of them.

Before this decision:

- **Players:** IDs are ours (`identity.players`), but only Sofascore creates them, and every rule matches into a Sofascore player (`rules.py`).
- **Clubs:** ADR 33 made Reep's team ID the Club ID.
- **Matches:** the Match ID is built from the Club IDs, so it inherits that dependency.
- **The Reep load (ADR 32, ADR 33):** keeps only persons and teams that have a Sofascore bridge.

A first draft of this ADR let any source mint any entity, with club slugs minted automatically. A review (on #66) showed why that fails:

- Transfermarkt and Understat share no strong signal without Sofascore. Understat has no birth dates, and Transfermarkt has no Appearances. So they would mint duplicate Players, and ingest lag between sources makes that happen even with Sofascore present.
- Automatic slugs depend on which source names a club first: 10 of 25 clubs have different names across sources, such as "Wolverhampton" and "Wolverhampton Wanderers".
- Club links do not fit `identity_candidates`, which is built for Players.

## Decision
- **Canonical IDs are ours,** kept in the Alembic-managed `identity` schema (ADR 31). They never change once given, and are never a source's or Reep's ID. A source's ID is only ever a link to one of ours.
- **Clubs.**
  - **The ID is a readable slug that a person chooses** when the Club is added: `arsenal`, `wolves`, `brighton`. It is ASCII, lower case and hyphenated. Same-named clubs are told apart by place (`arsenal-sarandi`), never by a counter. The display name is a separate, updatable column.
  - **`identity.clubs`** holds the Clubs. **`identity.club_links`** holds `(source, source_team_id, club_id)`, one link per source team.
  - **A command proposes links.** It looks at source teams with no link and proposes one from Reep (another source's team in the same Reep team is already linked) or from fixtures (a Match on the same date with the same score is already linked on the other source). A person confirms each proposal, or adds a new Club. That is about three Clubs per league per season. There is no fuzzy name matching: "Manchester United" and "Manchester City" defeat it.
  - **The 25 current Clubs** move from the dbt seed into these tables, with its slugs and its three sources' IDs as links. The seed is then deleted, as ADR 33 decided.
- **Competitions.** **`identity.competitions`** holds a slug we choose (`premier-league`). A small link table maps each source's competition ID to it: Sofascore 17, Understat `EPL`, Transfermarkt `GB1`. Both are added by hand when we take on a competition.
- **Matches.** The ID is `<competition>[:<stage>]:<season>:<home club>:<away club>`, such as `premier-league:2025:arsenal:chelsea`.
  - It is built in dbt, only from our own IDs.
  - The stage is added only for competitions where a home and away pair can meet twice in a season (split-phase leagues, play-offs).
  - dbt's `unique` test on the Match ID guards it: a competition that breaks the key fails the build until it gets a stage.
  - Season stays the start year. A calendar-year league uses its single year.
- **Players.**
  - **IDs stay ours** (`identity.players`).
  - **One configured anchor source mints Players:** `IDENTITY__ANCHOR`, today `sofascore`, because it carries birth dates and full lineups. The other sources link to Players; they never mint. Understat can never be the anchor, since it has no birth dates.
  - **Switching the anchor** is a deliberate change made when the anchor source is lost. It needs the rules to target Players rather than the anchor's IDs. Rewriting them is part of that switch; until then, today's rules stay.
  - **Merging duplicate Players** (retire and redirect) is left to its own ADR, when one is needed.
- **Reep stays the first mapping layer** (ADR 32), for Players, and as a proposal source for Club links. Its load keeps bridges for **every provider we ingest**, not only persons and teams with a Sofascore bridge. Losing Sofascore therefore does not empty it.
- **Transform Run (ADR 31), four steps:**
  1. `dbt build` of staging.
  2. **Club links.** The club command's proposals are confirmed before a run, so this step only checks that every source team in staging has a link, and fails listing the ones without.
  3. `dbt build` of what reads Club links: Clubs and Matches.
  4. Identity Resolution for Players, then `dbt build` of the rest.

  No step re-derives Matches in Python.

## Consequences
- **Losing a source keeps every ID.** Its link columns stop growing. Losing the Player anchor means switching it, deliberately, as above.
- **IDs are readable** (`arsenal`, `premier-league:2025:arsenal:chelsea`) and reproducible, because a person chose them and they live in `identity`, which is backed up as the only source of truth for them.
- **A person confirms new Clubs,** a few a season, through the club command.
- **New `identity` tables:** `clubs`, `club_links`, `competitions`, `competition_links`. `identity_candidates` stays Players-only.
- **Today's Match IDs gain the competition prefix.** The slugs are the seed's, so `2025:arsenal:chelsea` becomes `premier-league:2025:arsenal:chelsea`.
- **ADR 33 is superseded.** Its Reep team IDs as Club IDs are replaced. Loading team bridges is kept, as a link-proposal input, and the seed stays deleted.
- **ADR 32 is amended:**
  - the Reep load keeps bridges for every provider we ingest;
  - Sofascore anchors Players as the configured anchor, not as a fixed rule.
- **ADR 31 is amended:** the Transform Run has four steps.
- **Rejected:**
  - **Any source mints any entity.** It creates duplicate Players, and order-dependent club slugs.
  - **Sofascore's or Reep's IDs as canonical IDs.** They tie the platform to one of them.
  - **Automatically minted club slugs.** They are not reproducible and depend on which source is processed first.
  - **Opaque surrogate IDs for Clubs and Matches.** They are stable, but a confirmed slug costs a few decisions a season and serves citations far better.
