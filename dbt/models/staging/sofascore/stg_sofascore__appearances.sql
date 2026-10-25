-- One row per player with minutes in a finished Match. Unused substitutes have no minutes
-- and no statistics, so they are not Appearances.
with lineups as (
    select
        substring(url from '/api/v1/event/([0-9]+)/lineups$')::bigint as match_id,
        body_json
    from {{ ref('base_sofascore__responses') }}
    where url ~ '/api/v1/event/[0-9]+/lineups$'
),

entries as (
    select lineups.match_id, side.side, entry
    from lineups
    cross join lateral (values ('home'), ('away')) as side (side)
    cross join lateral jsonb_array_elements(lineups.body_json -> side.side -> 'players') as entry
)

select
    entries.match_id || '-' || (entry -> 'player' ->> 'id') as appearance_id,
    entries.match_id,
    (entry -> 'player' ->> 'id')::bigint as player_id,
    entry -> 'player' ->> 'name' as player_name,
    entries.side,
    case entries.side
        when 'home' then matches.home_team_id
        else matches.away_team_id
    end as team_id,
    entry ->> 'position' as position,
    (entry ->> 'substitute')::boolean as substitute,
    (entry -> 'statistics' ->> 'minutesPlayed')::int as minutes_played,
    (entry -> 'statistics' ->> 'rating')::numeric as rating,
    entry -> 'statistics' as statistics
from entries
inner join {{ ref('stg_sofascore__matches') }} as matches on matches.match_id = entries.match_id
where entry -> 'statistics' ? 'minutesPlayed'
