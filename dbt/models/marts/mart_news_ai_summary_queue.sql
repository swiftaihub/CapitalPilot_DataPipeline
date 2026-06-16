{{ config(
    materialized='table',
    schema='marts',
    tags=['mart', 'ai_queue', 'news']
) }}

with articles as (

    select *
    from {{ ref('int_news_deduped') }}

),

ai_latest as (

    select
        *,
        row_number() over (
            partition by summary_date, category, headline
            order by updated_at desc nulls last, created_at desc nulls last
        ) as rn
    from {{ source('ai', 'news_summaries') }}

)

select
    articles.article_id,
    articles.published_date as summary_date,
    articles.category,
    cast(null as varchar) as ticker,
    articles.title as headline,
    articles.url,
    articles.publisher,
    articles.published_at,
    articles.raw_summary,
    articles.raw_sentiment,
    articles.related_tickers_json,
    case
        when ai_latest.summary_id is not null
         and coalesce(ai_latest.bull_bear_label, '') <> 'insufficient_data'
            then 'completed'
        else 'pending'
    end as summary_status,
    ai_latest.summary_id,
    ai_latest.updated_at as summary_updated_at,
    current_timestamp as queued_at
from articles
left join ai_latest
  on articles.published_date = ai_latest.summary_date
 and articles.category = ai_latest.category
 and articles.title = ai_latest.headline
 and ai_latest.rn = 1
