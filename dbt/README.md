# CapitalPilot dbt Project

This dbt project transforms raw Phase 1 data into Streamlit-ready marts.

- `raw.raw_macro_observations` is loaded by `jobs/refresh_macro.py`.
- `raw.raw_prices` is loaded by `jobs/refresh_prices.py`.
- `marts.mart_sec_filing_placeholder` exists only to make the Phase 2 SEC Filing Agent visible in the data model.

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

