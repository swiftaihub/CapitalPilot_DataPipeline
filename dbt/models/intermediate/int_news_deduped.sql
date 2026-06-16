{{ config(
    materialized='table',
    schema='intermediate',
    tags=['intermediate', 'news']
) }}

with ranked as (

    select
        *,
        row_number() over (
            partition by article_id
            order by updated_at desc nulls last
        ) as rn
    from {{ ref('stg_news_articles') }}

)

select
    article_id,
    source_provider,
    publisher,
    title,
    url,
    published_at,
    cast(published_at as date) as published_date,
    category,
    query,
    related_tickers_json,
    raw_summary,
    raw_sentiment,
    raw_payload_json,
    updated_at
from ranked
where rn = 1

