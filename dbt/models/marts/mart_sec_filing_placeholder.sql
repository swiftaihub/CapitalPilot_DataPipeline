{{ config(
    materialized='table',
    schema='marts',
    tags=['mart', 'dashboard', 'sec', 'placeholder']
) }}

select
    'planned_phase_2' as status,
    'SEC Filing Agent placeholder' as feature_name,
    'Full SEC EDGAR ingestion, filing text extraction, risk factor diffing, and MCP-powered AI research are planned for Phase 2.' as message,
    cast(null as date) as latest_filing_date,
    current_timestamp as updated_at
