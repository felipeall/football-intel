-- One row per player with minutes in a played Match, from the Match's rosters.
with match_data as (
    select
        substring(url from '/getMatchData/([0-9]+)$')::bigint as match_id,
        body_json
    from {{ ref('base_understat__responses') }}
    where url ~ '/getMatchData/[0-9]+$'
),

entries as (
    select match_data.match_id, side.side, roster.value as entry
    from match_data
    cross join lateral (values ('h'), ('a')) as side (side)
    cross join lateral jsonb_each(match_data.body_json -> 'rosters' -> side.side) as roster
)

select
    (entry ->> 'id')::bigint as appearance_id,
    entries.match_id,
    (entry ->> 'player_id')::bigint as player_id,
    entry ->> 'player' as player_name,
    (entry ->> 'team_id')::bigint as team_id,
    case entries.side when 'h' then 'home' else 'away' end as side,
    entry ->> 'position' as position,
    (entry ->> 'time')::int as minutes_played,
    (entry ->> 'goals')::int as goals,
    (entry ->> 'assists')::int as assists,
    (entry ->> 'shots')::int as shots,
    (entry ->> 'key_passes')::int as key_passes,
    (entry ->> 'xG')::numeric as xg,
    (entry ->> 'xA')::numeric as xa,
    (entry ->> 'xGChain')::numeric as xg_chain,
    (entry ->> 'xGBuildup')::numeric as xg_buildup
from entries
inner join {{ ref('stg_understat__matches') }} as matches on matches.match_id = entries.match_id
where (entry ->> 'time')::int > 0
