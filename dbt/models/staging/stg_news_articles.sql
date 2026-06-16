{{ config(
    materialized='view',
    schema='staging',
    tags=['staging', 'news']
) }}

select
    article_id,
    lower(trim(source_provider)) as source_provider,
    publisher,
    title,
    url,
    cast(published_at as timestamp) as published_at,
    lower(trim(category)) as category,
    query,
    related_tickers_json,
    raw_summary,
    raw_sentiment,
    raw_payload_json,
    cast(updated_at as timestamp) as updated_at
from {{ source('raw', 'raw_news_articles') }}
where article_id is not null

