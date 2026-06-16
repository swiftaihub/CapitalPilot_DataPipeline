{{ config(
    materialized='table',
    schema='intermediate',
    tags=['intermediate', 'news']
) }}

select
    published_date as summary_date,
    category,
    count(*) as article_count,
    max(published_at) as latest_published_at,
    string_agg(title, ' | ' order by published_at desc) as headlines_joined
from {{ ref('int_news_deduped') }}
group by 1, 2

