-- Transfermarkt players from the batched `/players` responses of the squad fan-out, with
-- their current club.
with players as (
    select player, responses.captured_at
    from {{ ref('base_transfermarkt__responses') }} as responses
    cross join lateral jsonb_array_elements(responses.body_json -> 'data') as player
    where responses.url ~ '^https://tmapi\.transfermarkt\.technology/players\?'
)

select distinct on ((player ->> 'id')::bigint)
    (player ->> 'id')::bigint as player_id,
    player ->> 'name' as name,
    (player -> 'lifeDates' ->> 'dateOfBirth')::date as birth_date,
    player -> 'attributes' -> 'position' ->> 'name' as position,
    player -> 'attributes' ->> 'positionGroup' as position_group,
    player -> 'attributes' -> 'preferredFoot' ->> 'name' as preferred_foot,
    (
        select (assignment ->> 'clubId')::bigint
        from jsonb_array_elements(player -> 'clubAssignments') as assignment
        where assignment ->> 'type' = 'current'
        limit 1
    ) as current_club_id
from players
order by (player ->> 'id')::bigint, captured_at desc
