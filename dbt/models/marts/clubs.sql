-- Canonical Clubs, from the hand-mapped seed.
select club_id, name, sofascore_team_id, understat_team_id, transfermarkt_club_id
from {{ ref('club_source_ids') }}
