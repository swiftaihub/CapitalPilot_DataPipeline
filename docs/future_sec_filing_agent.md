# SEC Filing Pipeline

Phase 2 adds EDGAR ingestion and AI-ready SEC summary contracts inside
CapitalPilot_DataPipeline.

Implemented/owned here:

1. SEC ticker-to-CIK mapping ingestion.
2. SEC submissions API filing metadata for `10-K`, `10-Q`, and `8-K`.
3. Optional primary document download.
4. Raw SEC tables and dbt staging/intermediate/mart models.
5. `marts.mart_sec_ai_summary_queue` for `CapitalPilot_AI`.
6. `ai.sec_filing_summaries` schema for structured AI outputs.
7. Internal Streamlit observability for SEC freshness, rows, alerts, and queue
   status.

Owned by `CapitalPilot_AI`:

1. Filing section parsing if LLM-assisted.
2. Risk-factor diffing if LLM-assisted.
3. Prompt orchestration and model selection.
4. Writing structured summaries into `ai.sec_filing_summaries`.
5. Any future MCP/tool-calling interface.

This repo does not implement interactive SEC chat or an MCP research agent.
