-- Canonical Clubs (ADR 33): every Reep team that a stored Sofascore or Understat Match
-- names, with its Sofascore, Understat and Transfermarkt IDs from the pinned Reep release,
-- and its latest Sofascore name (Understat's when Sofascore has none). A team Reep does not
-- map has no Club, and fails the Match tests.
with bridges as (
    select reep_id, provider, external_id
    from {{ source('reference', 'reep_team_bridges') }}
    where release = '{{ env_var("REEP__RELEASE") }}'
),

teams as (
    select 'sofascore' as provider, home_team_id as team_id, home_team_name as name, kickoff_at
    from {{ ref('stg_sofascore__matches') }}
    union all
    select 'sofascore', away_team_id, away_team_name, kickoff_at
    from {{ ref('stg_sofascore__matches') }}
    union all
    select 'understat', home_team_id, home_team_name, kickoff_at
    from {{ ref('stg_understat__matches') }}
    union all
    select 'understat', away_team_id, away_team_name, kickoff_at
    from {{ ref('stg_understat__matches') }}
),

named as (
    select distinct on (bridges.reep_id)
        bridges.reep_id,
        teams.name
    from teams
    inner join bridges
        on bridges.provider = teams.provider and bridges.external_id = teams.team_id::text
    order by bridges.reep_id, teams.provider = 'sofascore' desc, teams.kickoff_at desc
)

select
    named.reep_id as club_id,
    named.name,
    max(bridges.external_id) filter (where bridges.provider = 'sofascore')::bigint
        as sofascore_team_id,
    max(bridges.external_id) filter (where bridges.provider = 'understat')::bigint
        as understat_team_id,
    max(bridges.external_id) filter (where bridges.provider = 'transfermarkt')::bigint
        as transfermarkt_club_id
from named
inner join bridges on bridges.reep_id = named.reep_id
group by named.reep_id, named.name
