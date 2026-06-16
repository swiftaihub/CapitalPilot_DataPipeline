# AI Boundary and Data Contracts

CapitalPilot_DataPipeline no longer plans to host an interactive MCP research
agent or end-user AI chat.

The production split is:

- `CapitalPilot_DataPipeline`: source ingestion, raw/staging/intermediate/mart
  schemas, dbt transformations, scheduled refresh jobs, AI queue tables, AI
  output table schemas, and internal pipeline observability.
- `CapitalPilot_AI`: LLM orchestration, summarization prompts, tool-calling or
  MCP-style orchestration if needed, and writes to `ai.*` output tables.
- `CapitalPilot_UI`: user-facing frontend that reads marts and AI summaries.

## DataPipeline AI Contracts

DataPipeline produces queue marts:

- `marts.mart_sec_ai_summary_queue`
- `marts.mart_news_ai_summary_queue`

DataPipeline owns the destination table schemas:

- `ai.sec_filing_summaries`
- `ai.news_summaries`

`CapitalPilot_AI` may read queue rows, generate structured summaries, and write
results back into those `ai.*` tables. DataPipeline should not perform live
interactive chat, user-facing LLM research, brokerage actions, or portfolio
execution.

## Guardrails

- No deterministic buy/sell recommendations.
- No trading or brokerage integration.
- Preserve source URLs, raw payloads, timestamps, and uncertainty.
- Political disclosures may be delayed, incomplete, and range-based.
- House PTR ingestion uses the official House Clerk XML index and public PTR
  PDFs. Senate eFD and OGE automation should be added only when source access is
  reliable and terms-compatible.
- News sentiment and AI summaries are interpretations and may be wrong.
