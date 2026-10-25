-- Every player with an Understat Appearance. Understat has no birth dates.
select distinct on (player_id)
    player_id,
    player_name as name
from {{ ref('stg_understat__appearances') }}
order by player_id, match_id desc
