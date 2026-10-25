-- The latest successful Raw Response per Transfermarkt URL. Read as raw JSON here, not
-- replayed through the SDK (ADR 28): staging only needs fields the JSON API returns as is.
select distinct on (url)
    url,
    body_json,
    captured_at
from {{ source('raw', 'raw_responses') }}
where source = 'transfermarkt'
    and status_code = 200
order by url, captured_at desc
