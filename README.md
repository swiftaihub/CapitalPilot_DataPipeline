# CapitalPilot_DataPipeline

CapitalPilot_DataPipeline is the ingestion, transformation, scheduling, and
observability repo for CapitalPilot research data.

It is for personal research only. It is not financial advice, does not automate
trading, does not connect to brokerage APIs, and does not produce deterministic
buy/sell recommendations.

## Three-Repo Boundary

CapitalPilot is split into three repos:

- `CapitalPilot_DataPipeline`: source ingestion, raw/staging/intermediate/mart
  schemas, dbt transformations, scheduled refresh jobs, AI queue contracts, AI
  output table schemas, and internal Streamlit observability.
- `CapitalPilot_AI`: LLM orchestration, summarization, prompt versions,
  AI-as-tool refresh logic, and any future MCP/tool-calling implementation.
- `CapitalPilot_UI`: final user-facing frontend that reads marts and AI summary
  tables.

This repo does not host an interactive MCP research agent or end-user AI chat.
`CapitalPilot_AI` reads queue marts from this repo, writes structured summaries
to `ai.*` tables, and `CapitalPilot_UI` displays those outputs.

## Phase 2 Capabilities

- FRED macro ingestion and yfinance price ingestion from Phase 1.
- SEC `10-K`, `10-Q`, and `8-K` metadata ingestion from EDGAR, plus optional
  filing document download.
- Configurable daily news metadata ingestion with manual CSV and optional Alpha
  Vantage provider support.
- Public political/high-official disclosure schema with manual CSV ingestion and
  documented Senate, House, and OGE source scaffolds.
- Long-term accumulation research indicators.
- Options math and optional option-chain schema/provider.
- Daily technical indicators and market summary marts.
- Ops metadata tables for runs, tasks, errors, and freshness checks.
- Internal Streamlit pipeline dashboard.

## AI Contracts

Queue marts produced by dbt:

- `marts.mart_sec_ai_summary_queue`
- `marts.mart_news_ai_summary_queue`

AI output tables created by DataPipeline and written by `CapitalPilot_AI`:

- `ai.sec_filing_summaries`
- `ai.news_summaries`

Summary labels should stay research-oriented, such as `bullish`, `bearish`,
`mixed`, `neutral`, and `unknown`. They must not become deterministic trading
instructions.

## Data Sources and Limits

- SEC: free EDGAR endpoints using `SEC_USER_AGENT`; fair-access retry, timeout,
  and rate limiting are enforced in `src/sec_client.py`.
- Macro: FRED API through `FRED_API_KEY`.
- Prices: yfinance daily history.
- News: manual CSV works offline; Alpha Vantage `NEWS_SENTIMENT` is optional.
  Future documented options include Finnhub, Benzinga, GDELT, and permitted RSS.
- Political disclosures: manual CSV ingestion works now. Senate, House, and OGE
  sources often involve PDFs, search forms, and delayed range disclosures, so
  exact holdings must not be inferred. House Periodic Transaction Reports can be
  ingested automatically from the official House Clerk yearly XML index and PTR
  PDFs.
- Options: Black-Scholes, Greeks, payoff, and vertical-spread calculators are
  deterministic. yfinance option-chain ingestion is optional and disabled by
  default.

## Local Setup

Python 3.11 is recommended and declared in `runtime.txt`.

```bash
pip install -r requirements.txt
cp dbt/profiles.yml.example dbt/profiles.yml
python jobs/run_pipeline.py --target local --run-dbt
streamlit run app.py
```

Individual jobs:

```bash
python jobs/refresh_macro.py --target local
python jobs/refresh_prices.py --target local
python jobs/refresh_sec_filings.py --target local --forms 10-K,10-Q,8-K
python jobs/refresh_news.py --target local --provider manual
python jobs/refresh_political_trades.py --target local --source manual --manual-file tests/fixtures/political_transactions_sample.csv
python jobs/refresh_political_trades.py --target local --source house --days-back 120 --max-reports 5
python jobs/refresh_options.py --target local --force
```

Optional jobs skip gracefully in `jobs/run_pipeline.py` when source secrets or
providers are unavailable. Direct SEC refresh requires a valid `SEC_USER_AGENT`.
The House official-trades source downloads public PTR PDFs, so start with a
small `--max-reports` value before widening the date range.

## MotherDuck

```bash
export CAPITALPILOT_DB_TARGET=motherduck
export MOTHERDUCK_TOKEN=your_token
export FRED_API_KEY=your_fred_key
export SEC_USER_AGENT="CapitalPilot contact@yourdomain.com"

python jobs/run_pipeline.py --target motherduck --run-dbt
```

## Secrets

Required for production MotherDuck:

- `MOTHERDUCK_TOKEN`

Required for specific source jobs:

- `FRED_API_KEY` for macro refresh.
- `SEC_USER_AGENT` for SEC refresh.

Optional:

- `ALPHA_VANTAGE_API_KEY` for Alpha Vantage news.
- Other future news provider keys.

LLM keys belong in `CapitalPilot_AI`, not this repo.

## GitHub Actions

`.github/workflows/refresh_capitalpilot.yml` runs Python 3.11, installs
dependencies, validates dbt, runs:

```bash
python jobs/run_pipeline.py --target motherduck --run-dbt
```

Then it generates dbt docs and uploads dbt artifacts. Configure these GitHub
secrets as applicable:

- `MOTHERDUCK_TOKEN`
- `FRED_API_KEY`
- `SEC_USER_AGENT`
- `ALPHA_VANTAGE_API_KEY`

## Internal Dashboard

`streamlit run app.py` opens the internal DataPipeline observability console. It
shows:

- database target and connection status
- latest pipeline/task run status
- latest refresh/freshness by domain
- row counts by raw, mart, and AI contract tables
- recent errors
- recent records by domain
- AI summary queue counts

The Streamlit app is not the final user-facing UI.

## dbt

Local:

```bash
cd dbt
dbt build --profiles-dir . --target dev
```

Production:

```bash
cd dbt
dbt build --profiles-dir . --target prod
```

Schemas:

- `raw`
- `staging`
- `intermediate`
- `marts`
- `ai`
- `ops`

## Tests

```bash
pytest
```

Tests use fixtures and mocks; they do not require live external API calls.

## Disclaimers

CapitalPilot is personal research software only. It is not investment advice.
It does not automate trading, execute orders, connect to brokerage accounts, or
produce deterministic buy/sell recommendations. Political disclosures may be
delayed, incomplete, and range-based. News sentiment and AI summaries are model
interpretations and may be wrong.
