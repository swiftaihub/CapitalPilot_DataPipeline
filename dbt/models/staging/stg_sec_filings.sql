{{ config(
    materialized='view',
    schema='staging',
    tags=['staging', 'sec']
) }}

select
    upper(trim(ticker)) as ticker,
    lpad(cast(cik as varchar), 10, '0') as cik,
    accession_number,
    upper(trim(form_type)) as form_type,
    cast(filing_date as date) as filing_date,
    cast(report_date as date) as report_date,
    cast(acceptance_datetime as timestamp) as acceptance_datetime,
    primary_document,
    filing_detail_url,
    document_url,
    document_text,
    source,
    raw_payload_json,
    cast(updated_at as timestamp) as updated_at
from {{ source('raw', 'raw_sec_filings') }}
where accession_number is not null
  and ticker is not null

