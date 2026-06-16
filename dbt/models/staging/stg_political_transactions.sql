{{ config(
    materialized='view',
    schema='staging',
    tags=['staging', 'political']
) }}

select
    transaction_id,
    official_name,
    role,
    lower(trim(branch)) as branch,
    chamber,
    party,
    state,
    nullif(upper(trim(ticker)), '') as ticker,
    asset_name,
    asset_type,
    lower(trim(transaction_type)) as transaction_type,
    cast(transaction_date as date) as transaction_date,
    cast(notification_date as date) as notification_date,
    cast(filing_date as date) as filing_date,
    cast(amount_min as double) as amount_min,
    cast(amount_max as double) as amount_max,
    amount_text,
    owner,
    source_report_id,
    source_url,
    source_pdf_url,
    raw_payload_json,
    cast(confidence_score as double) as confidence_score,
    cast(updated_at as timestamp) as updated_at
from {{ source('raw', 'raw_political_transactions') }}
where transaction_id is not null

