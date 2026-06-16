{{ config(
    materialized='table',
    schema='marts',
    tags=['mart', 'ai_queue', 'sec']
) }}

with filings as (

    select *
    from {{ ref('int_recent_sec_filings') }}
    where form_type in ('10-K', '10-Q', '8-K')

),

documents as (

    select
        *,
        row_number() over (
            partition by accession_number
            order by
                case when download_status = 'completed' then 0 else 1 end,
                updated_at desc nulls last
        ) as rn
    from {{ ref('stg_sec_filing_documents') }}

),

ai_latest as (

    select
        *,
        row_number() over (
            partition by accession_number, summary_type
            order by updated_at desc nulls last, created_at desc nulls last
        ) as rn
    from {{ source('ai', 'sec_filing_summaries') }}

)

select
    filings.ticker,
    filings.cik,
    filings.accession_number,
    filings.form_type,
    filings.filing_date,
    coalesce(documents.document_text, filings.document_text) as document_text,
    substr(coalesce(documents.document_text, filings.document_text, ''), 1, 50000) as document_text_truncated,
    filings.filing_detail_url,
    filings.document_url,
    case
        when ai_latest.summary_id is not null
         and coalesce(ai_latest.market_impact_label, ai_latest.business_impact, '') <> 'insufficient_data'
            then 'completed'
        when documents.download_status = 'failed' then 'failed'
        when coalesce(documents.document_text, filings.document_text) is null then 'pending_document'
        else 'pending'
    end as summary_status,
    ai_latest.summary_id,
    ai_latest.updated_at as summary_updated_at,
    current_timestamp as queued_at
from filings
left join documents
  on filings.accession_number = documents.accession_number
 and documents.rn = 1
left join ai_latest
  on filings.accession_number = ai_latest.accession_number
 and ai_latest.rn = 1
