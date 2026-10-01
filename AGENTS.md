# AGENTS.md — SentinelReg

Instructions for Snowflake CoCo CLI (Cortex Code) when operating in this repository.

## Project

SentinelReg is an AML Risk, Fraud & Regulatory Intelligence Copilot for banking/NBFC
compliance teams, built for the Snowflake CoCo CLI Hackathon 2026 (GCC Edition),
problem statement: **Risk, Fraud & Regulatory Intelligence Copilot**.

It combines:
- **Cortex Analyst** — natural-language → SQL over `TRANSACTIONS`, `ACCOUNTS`, `AML_ALERTS`,
  `ML_RISK_FEATURES`, and `REGULATORY_DOCS_CHUNKS` (chunked RBI / FATF / Basel / FinCEN text,
  queried via SQL/ILIKE rather than Cortex Search — see below)
- **Snowflake ML (Snowpark ML)** — gradient-boosted fraud classifier producing `COMPUTED_RISK_SCORE`,
  surfaced live in the Risk Dashboard against the rule-based `RISK_SCORE`
- **Streamlit** — overview, alert triage, investigation copilot, Entity 360, network map, regulatory library, SAR generator and hash-chained audit trail
- **Demo mode** — with no usable Snowflake credentials (or `SENTINEL_DEMO_MODE=1`) the app runs from `app/data/demo_snapshot.json`, generated from `setup/03` + `setup/04` by `scripts/build_demo_snapshot.py`

> Cortex Search is intentionally not used: it depends on `EMBED_TEXT_768`, which is
> unavailable on trial accounts. `setup/04_cortex_search.sql` has the Cortex Search
> definition commented out for anyone running this on a paid account later.

## Repo map

| Path | Purpose |
|---|---|
| `setup/01-04_*.sql` | Run in order to provision DB, tables, synthetic data, regulatory chunks. `05_create_agent.sql` is optional — the app calls Cortex Analyst directly and doesn't need it. |
| `semantic_model/aml_risk_model.yaml` | Cortex Analyst semantic model |
| `regulatory_docs/*.md` | Source regulatory text (chunked into `REGULATORY_DOCS_CHUNKS` by `setup/04_cortex_search.sql`) |
| `ml_pipeline/fraud_classifier.py` | Trains/scores the Snowpark ML fraud classifier |
| `app/` | Streamlit application (`main.py`, `views/`, `utils/`). The page modules live in `app/views/`, not `app/pages/` — Streamlit reserves the `pages/` directory name for its own auto-discovery, which collides with the explicit `st.navigation`/`st.Page` routing this app uses in `main.py`. |
| `app/utils/data.py` | Single data-access layer (live Snowflake and demo snapshot return identical shapes) |
| `tests/` | `SENTINEL_DEMO_MODE=1 pytest tests/` — page renders, flows, and live SQL executed against DuckDB |
| `.coco/skills/` | CoCo CLI Agent Skills scoped to this project |

## Conventions

- All Snowflake object names are UPPER_SNAKE_CASE; Python is standard PEP8.
- SQL setup scripts are idempotent (`CREATE OR REPLACE`) and must stay runnable end-to-end
  in order 01 → 04 against a fresh account (05 is optional, see above).
- Never commit real credentials — only `.env.example` is tracked; `.env` is gitignored.
- When adding a new fraud typology, update in this order: `setup/02_create_tables.sql`
  (if new columns needed) → `setup/03_load_synthetic_data.sql` (scenario data) →
  `ml_pipeline/fraud_classifier.py` (if it's a new ML feature) →
  `semantic_model/aml_risk_model.yaml` (so Cortex Analyst can query it) →
  `app/utils/risk_signals.py` (if it needs a reusable detection rule).
- Regulatory citations in the UI and generated SARs must trace back to a row in
  `REGULATORY_DOCS_CHUNKS` — never let the agent fabricate a citation. `utils/narrative.py::enforce_citations` strips any bracketed ID not in the supplied clauses.
- After changing `setup/03` or `setup/04`, re-run `python scripts/build_demo_snapshot.py`.

## Common tasks

- **Provision the Snowflake backend:** run `setup/01_setup_db.sql` through
  `setup/04_cortex_search.sql` in order via `coco run` or `snowsql -f`
  (`05_create_agent.sql` is optional, see above).
- **Run the app locally:** `pip install -r requirements.txt && streamlit run app/main.py`
  from the repo root (or `app/` — see README Quick Start).
- **Retrain the fraud classifier:** `python ml_pipeline/fraud_classifier.py`.
- **Add a fraud scenario for the demo:** extend `setup/03_load_synthetic_data.sql`
  with new `TRANSACTIONS` + one `AML_ALERTS` row + one `ML_RISK_FEATURES` row.
