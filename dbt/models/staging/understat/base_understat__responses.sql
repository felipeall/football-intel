-- The latest successful Raw Response per Understat URL. Failures (a 404 for a Match's data,
-- say) and earlier copies of a re-fetched URL are left out.
select distinct on (url)
    url,
    body_json,
    captured_at
from {{ source('raw', 'raw_responses') }}
where source = 'understat'
    and status_code = 200
order by url, captured_at desc
