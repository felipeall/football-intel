-- Canonical Matches across Sofascore and Understat. In a league season each (home Club, away
-- Club) pair plays once, so that key links the sources, whatever their kickoff times say.
-- A Match one source has not stored yet keeps the other's side only.
with sofascore as (
    select
        split_part(matches.season_year, '/', 1)::int + 2000 as season,
        home.club_id as home_club_id,
        away.club_id as away_club_id,
        matches.match_id,
        matches.kickoff_at,
        matches.home_goals,
        matches.away_goals
    from {{ ref('stg_sofascore__matches') }} as matches
    left join {{ ref('club_source_ids') }} as home on home.sofascore_team_id = matches.home_team_id
    left join {{ ref('club_source_ids') }} as away on away.sofascore_team_id = matches.away_team_id
),

understat as (
    select
        matches.season,
        home.club_id as home_club_id,
        away.club_id as away_club_id,
        matches.match_id,
        matches.kickoff_at,
        matches.home_goals,
        matches.away_goals
    from {{ ref('stg_understat__matches') }} as matches
    left join {{ ref('club_source_ids') }} as home on home.understat_team_id = matches.home_team_id
    left join {{ ref('club_source_ids') }} as away on away.understat_team_id = matches.away_team_id
)

select
    coalesce(sofascore.season, understat.season)
    || ':' || coalesce(sofascore.home_club_id, understat.home_club_id)
    || ':' || coalesce(sofascore.away_club_id, understat.away_club_id) as match_id,
    coalesce(sofascore.season, understat.season) as season,
    coalesce(sofascore.home_club_id, understat.home_club_id) as home_club_id,
    coalesce(sofascore.away_club_id, understat.away_club_id) as away_club_id,
    coalesce(sofascore.kickoff_at, understat.kickoff_at) as kickoff_at,
    coalesce(sofascore.home_goals, understat.home_goals) as home_goals,
    coalesce(sofascore.away_goals, understat.away_goals) as away_goals,
    sofascore.match_id as sofascore_match_id,
    understat.match_id as understat_match_id,
    sofascore.home_goals as sofascore_home_goals,
    sofascore.away_goals as sofascore_away_goals,
    understat.home_goals as understat_home_goals,
    understat.away_goals as understat_away_goals
from sofascore
full join understat
    on sofascore.season = understat.season
    and sofascore.home_club_id = understat.home_club_id
    and sofascore.away_club_id = understat.away_club_id
