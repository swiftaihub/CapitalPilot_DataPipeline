# CapitalPilot

CapitalPilot is a Streamlit cloud-deployable personal investment research terminal.

It is designed for personal research only. It is not financial advice, does not automate trading, does not connect to brokerage APIs, and does not produce deterministic buy/sell recommendations.

## Phase 1 Scope

Phase 1 implements the foundation:

- Project scaffold for Streamlit, Python ingestion jobs, DuckDB/MotherDuck, dbt, tests, docs, and GitHub Actions
- Local DuckDB development database at `data/capitalpilot.duckdb`
- MotherDuck production target at `md:capitalpilot`
- Raw macro observations from FRED
- Raw price history from yfinance
- dbt staging, intermediate, and mart models
- Macro Monitor MVP
- Valuation Engine MVP with price and market-cap data
- SEC Filing Agent placeholder page
- SEC service-layer placeholder functions
- Future MCP integration design documentation

## Intentionally Placeholder

These are planned for Phase 2 and are not implemented in Phase 1:

- Full SEC EDGAR ingestion
- SEC company facts ingestion
- SEC filing text extraction
- Filing section parsing
- Risk factor diffing
- MCP server
- Autonomous AI tool calling
- Live LLM execution against SEC data

## Architecture

```text
Python ingestion jobs
        |
MotherDuck raw tables
        |
dbt transformations
        |
MotherDuck staging / intermediate / marts
        |
Streamlit Cloud reads marts tables
        |
Future Phase 2: MCP server exposes read-only research tools to AI agent
```

Local development uses DuckDB at `data/capitalpilot.duckdb`. Production uses MotherDuck with `MOTHERDUCK_TOKEN`.

## Data Stack

- Python 3.11+
- Streamlit
- pandas / numpy
- plotly
- requests
- pydantic
- PyYAML
- duckdb
- dbt-core
- dbt-duckdb
- yfinance
- python-dotenv
- pytest

No MCP dependencies are included in Phase 1.

## Local Setup

Python 3.11 is recommended and is declared in `runtime.txt` for Streamlit Cloud. The dbt dependency stack may lag the newest CPython releases.

Check your local interpreter before creating the virtual environment:

```bash
python --version
```

On Windows, `py -0p` lists installed Python versions. If it only shows Python 3.14, install Python 3.11 and recreate `.venv`; a virtual environment created from Python 3.14 will still fail before dbt can parse the project.

```bash
pip install -r requirements.txt

python jobs/refresh_macro.py --target local
python jobs/refresh_prices.py --target local
python jobs/run_pipeline.py --target local --run-dbt

cp dbt/profiles.yml.example dbt/profiles.yml
cd dbt
dbt build --profiles-dir . --target dev
cd ..

streamlit run app.py
```

`refresh_macro.py` requires `FRED_API_KEY`. `refresh_prices.py` uses yfinance and does not require an API key.

## MotherDuck Setup

Set secrets in your shell or GitHub Actions environment:

```bash
export CAPITALPILOT_DB_TARGET=motherduck
export MOTHERDUCK_TOKEN=your_token
export FRED_API_KEY=your_fred_key

python jobs/refresh_macro.py --target motherduck
python jobs/refresh_prices.py --target motherduck

cd dbt
cp profiles.yml.example profiles.yml
dbt build --profiles-dir . --target prod
```

## Required Secrets

- `MOTHERDUCK_TOKEN`
- `FRED_API_KEY`

## Future Phase 2 Secrets

- `SEC_USER_AGENT`
- `OPENAI_API_KEY`

These future secrets are documented but not required for Phase 1.

## GitHub Actions

Two workflows are included:

- `.github/workflows/refresh_capitalpilot.yml` refreshes macro and price data, then runs dbt against MotherDuck.
- `.github/workflows/dbt_debug.yml` validates the dbt connection and builds selected models.

GitHub Actions cron uses UTC. The scheduled refresh runs at `22:30 UTC` Monday through Friday, roughly `6:30 PM New York time` during US daylight saving time.

Add these GitHub repository secrets before enabling scheduled production refresh:

- `MOTHERDUCK_TOKEN`
- `FRED_API_KEY`

SEC jobs are intentionally not included in Phase 1.

## Streamlit Cloud Deployment

1. Push the repository to GitHub.
2. Create a Streamlit Community Cloud app pointing to `app.py`.
3. Add Streamlit secrets from `.streamlit/secrets.toml.example`.
4. Use `MOTHERDUCK_TOKEN` in Streamlit secrets to read production marts from MotherDuck.

If `MOTHERDUCK_TOKEN` is not available, Streamlit falls back to local DuckDB if `data/capitalpilot.duckdb` exists.

## Dashboards

### Macro Monitor

Reads from `marts.mart_macro_dashboard`.

Includes rates, inflation, unemployment, dollar index, VIX, and a deterministic macro regime score. The score is a research signal only.

### Valuation Engine

Reads from `marts.mart_valuation_dashboard`.

Phase 1 includes latest price, market cap, volume, watchlist table, and price history. Fundamental metrics such as revenue, earnings, FCF, PE, PS, and FCF yield require SEC company facts and will be added in Phase 2.

### SEC Filing Agent

Phase 1 includes a professional placeholder dashboard with planned capabilities, example AI queries, non-functional prompt UI, and future MCP tool contract preview.

The placeholder includes these Phase 2 target queries:

- 帮我查一下 NVDA 最近三次 10-Q 里 risk factors 有什么变化
- 找出 watchlist 里最近 30 天有 8-K 的公司
- 比较 MRVL 和 AVGO 的 revenue growth、FCF yield 和最近 filing 风险
- 帮我基于 filings 和 valuation 生成一份本周 research brief

## Future MCP Section

Phase 2 will add a read-only MCP server exposing tools such as:

- `search_sec_filings`
- `get_recent_10q_risk_factor_changes`
- `find_watchlist_8k_filings`
- `compare_companies_research_snapshot`
- `generate_weekly_research_brief`
- `get_macro_snapshot`
- `get_valuation_snapshot`

Guardrails:

- Read-only only
- No trading
- No portfolio execution
- No database writes from AI agent
- No deterministic buy/sell recommendations
- Must say insufficient data if data is missing
- Must distinguish source data from interpretation

## SEC Filing Agent Phase 2 Roadmap

1. SEC EDGAR ingestion
2. Ticker-to-CIK mapping
3. Recent filing metadata
4. Company facts ingestion
5. Filing document download
6. Filing section parser
7. Risk factor extraction
8. Risk factor diffing
9. Thesis impact analysis
10. dbt SEC marts
11. MCP server
12. AI chat UI integration

## Testing

```bash
pytest
```

Tests do not require live API calls.

## Disclaimer

CapitalPilot is for personal research only. It is not investment advice. It does not automate trading, execute portfolio actions, connect to brokerage APIs, or produce deterministic buy/sell recommendations.
