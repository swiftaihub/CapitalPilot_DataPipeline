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
    primary_document,
    document_url,
    document_text,
    content_type,
    download_status,
    error_message,
    source,
    cast(updated_at as timestamp) as updated_at
from {{ source('raw', 'raw_sec_filing_documents') }}
where accession_number is not null

