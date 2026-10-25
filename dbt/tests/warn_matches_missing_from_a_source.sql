{{ config(severity='warn') }}
-- Matches one source has and the other has not stored yet. Expected while ingestion of
-- the current season runs at different times per source; listed, not failed.
select match_id, sofascore_match_id, understat_match_id
from {{ ref('matches') }}
where sofascore_match_id is null or understat_match_id is null
