-- Minutes per Sofascore player and season. Keyed by the Sofascore player until Identity
-- Resolution gives the canonical Player (ADR 6, ADR 31).
select
    appearances.player_id || '-' || matches.season_year as player_season_id,
    appearances.player_id,
    matches.season_year,
    count(*) as appearances,
    sum(appearances.minutes_played) as minutes_played
from {{ ref('stg_sofascore__appearances') }} as appearances
inner join {{ ref('stg_sofascore__matches') }} as matches using (match_id)
group by appearances.player_id, matches.season_year
