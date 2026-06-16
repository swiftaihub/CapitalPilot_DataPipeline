{{ config(
    materialized='table',
    schema='marts',
    tags=['mart', 'dashboard', 'sec', 'placeholder']
) }}

select
    'deprecated_placeholder' as status,
    'SEC data contract placeholder' as feature_name,
    'SEC ingestion and AI summary queue tables now live in Phase 2 DataPipeline models. Interactive AI and MCP-style tooling belong in CapitalPilot_AI, not this repo.' as message,
    cast(null as date) as latest_filing_date,
    current_timestamp as updated_at
