-- The latest successful Raw Response per Sofascore URL. Failures (a 403 challenge, say) and
-- earlier copies of a re-fetched URL are left out.
select distinct on (url)
    url,
    body_json,
    captured_at
from {{ source('raw', 'raw_responses') }}
where source = 'sofascore'
    and status_code = 200
order by url, captured_at desc
