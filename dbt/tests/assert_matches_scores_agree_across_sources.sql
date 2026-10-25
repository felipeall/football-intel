-- Where both sources have a Match, they agree on its score. A wrong club mapping would pair
-- different fixtures and show up here.
select match_id, sofascore_home_goals, sofascore_away_goals, understat_home_goals,
    understat_away_goals
from {{ ref('matches') }}
where sofascore_match_id is not null
    and understat_match_id is not null
    and (
        sofascore_home_goals <> understat_home_goals
        or sofascore_away_goals <> understat_away_goals
    )
