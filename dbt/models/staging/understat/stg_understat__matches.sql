-- Played Matches, from each season's league data. Understat names a season by its start
-- year; `season_year` writes it as Sofascore does ("25/26").
with seasons as (
    select
        substring(url from '/getLeagueData/([^/]+)/[0-9]+$') as league,
        substring(url from '/getLeagueData/[^/]+/([0-9]+)$')::int as season,
        body_json
    from {{ ref('base_understat__responses') }}
    where url ~ '/getLeagueData/[^/]+/[0-9]+$'
)

select
    (fixture ->> 'id')::bigint as match_id,
    seasons.league,
    seasons.season,
    lpad((seasons.season % 100)::text, 2, '0')
    || '/'
    || lpad(((seasons.season + 1) % 100)::text, 2, '0') as season_year,
    -- Understat's times are UTC.
    (fixture ->> 'datetime')::timestamp at time zone 'UTC' as kickoff_at,
    (fixture -> 'h' ->> 'id')::bigint as home_team_id,
    {{ html_unescape("fixture -> 'h' ->> 'title'") }} as home_team_name,
    (fixture -> 'a' ->> 'id')::bigint as away_team_id,
    {{ html_unescape("fixture -> 'a' ->> 'title'") }} as away_team_name,
    (fixture -> 'goals' ->> 'h')::int as home_goals,
    (fixture -> 'goals' ->> 'a')::int as away_goals,
    (fixture -> 'xG' ->> 'h')::numeric as home_xg,
    (fixture -> 'xG' ->> 'a')::numeric as away_xg
from seasons
cross join lateral jsonb_array_elements(seasons.body_json -> 'dates') as fixture
where (fixture ->> 'isResult')::boolean
