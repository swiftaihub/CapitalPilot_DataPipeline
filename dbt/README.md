# CapitalPilot dbt Project

This dbt project transforms raw CapitalPilot source tables into staging,
intermediate, mart, and AI queue tables.

- `raw.raw_macro_observations` is loaded by `jobs/refresh_macro.py`.
- `raw.raw_prices` is loaded by `jobs/refresh_prices.py`.
- `raw.raw_sec_filings` is loaded by `jobs/refresh_sec_filings.py`.
- `raw.raw_news_articles` is loaded by `jobs/refresh_news.py`.
- `raw.raw_political_transactions` is loaded by `jobs/refresh_political_trades.py`.
- `raw.raw_options_chain` is optionally loaded by `jobs/refresh_options.py`.
- `marts.mart_sec_ai_summary_queue` and `marts.mart_news_ai_summary_queue`
  are consumed by `CapitalPilot_AI`.

Interactive AI, MCP/tool-calling, and end-user UI behavior live outside this
DataPipeline repo.

Local build:

```bash
cp profiles.yml.example profiles.yml
dbt build --profiles-dir . --target dev
```

MotherDuck build:

```bash
cp profiles.yml.example profiles.yml
dbt build --profiles-dir . --target prod
```

