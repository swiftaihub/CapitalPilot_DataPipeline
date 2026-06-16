{{ config(
    materialized='table',
    schema='marts',
    tags=['mart', 'dashboard', 'news']
) }}

select
    summary_date,
    category,
    article_count,
    latest_published_at,
    headlines_joined,
    false as is_investment_advice
from {{ ref('int_daily_news_by_category') }}
order by summary_date desc, category

