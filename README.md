# 🛡️ SentinelReg — Risk, Fraud & Regulatory Intelligence Copilot

> An AI-native compliance copilot for Banking and NBFC teams — built on Snowflake Cortex AI and CoCo CLI.

[![Snowflake](https://img.shields.io/badge/Built%20on-Snowflake-29B5E8?style=flat&logo=snowflake)](https://snowflake.com)
[![Cortex](https://img.shields.io/badge/Powered%20by-Cortex%20AI-29B5E8?style=flat)](https://docs.snowflake.com/en/guides-overview-ai-features)
[![Streamlit](https://img.shields.io/badge/UI-Streamlit-FF4B4B?style=flat&logo=streamlit)](https://streamlit.io)

---

## Overview

**SentinelReg** is an enterprise-grade Risk, Fraud, and Regulatory Intelligence Copilot for Banking and NBFC operations teams. It unifies structured transaction data with unstructured regulatory documents (RBI AML Master Directions, Basel guidelines, FinCEN BSA/AML Manual) to surface fraud signals, explain them in natural language, and generate audit-ready regulatory outputs.

The system moves a compliance analyst from a raw alert all the way to a documented, evidence-backed Suspicious Activity Report (SAR) — in one natural language conversation.

---

## Key Capabilities

| Capability | Description |
|---|---|
| 🔍 **Natural Language Investigation** | Ask any question about accounts, transactions, or patterns in plain English |
| 🧠 **Unified Text-to-SQL Engine** | Cortex Analyst answers both transactional questions and regulatory questions (over `REGULATORY_DOCS_CHUNKS`) from one semantic model |
| ⚠️ **Real-Time Fraud Signal Detection** | Velocity checks, structuring patterns, round-trip transfers, shell account behavior |
| 📋 **SAR Report Generation** | One-click Suspicious Activity Report as audit-ready Markdown/PDF |
| 🏦 **Regulatory Compliance Grounding** | Every answer cites RBI / FinCEN policy clause |
| 📊 **Risk Command Dashboard** | Live view of high-risk accounts, alert heatmaps, AML typology breakdown |

---

## What's in the app

| Page | What it does |
|---|---|
| Overview | KPIs, priority queue with 7-day STR filing clocks, severity/exposure charts, fund-flow ring insight |
| Alert Triage | Human-in-the-loop dispositions (written back to `AML_ALERTS`), re-runnable detection engine (5 typologies), ML vs rule-based scores with reason codes |
| Investigation Copilot | Cortex Analyst text-to-SQL chat; deterministic offline router when Snowflake is unreachable |
| Entity 360 | KYC profile, accounts, risk drivers, transactions, alerts, 2-hop fund flow, applicable clauses |
| Network Intelligence | Graphviz fund-flow map; connected rings show separate alerts are one scheme |
| Regulatory Library | Ranked keyword search over `REGULATORY_DOCS_CHUNKS`, typology → clause map |
| SAR Generator | Cortex COMPLETE narrative with citation guardrail, PDF + evidence package (.zip with SHA-256 manifest), filing write-back |
| Audit Trail | SHA-256 hash-chained log of every decision, query and filing, with tamper detection |

**Demo mode:** without usable Snowflake credentials (or with `SENTINEL_DEMO_MODE=1`) the app runs on `app/data/demo_snapshot.json`, generated from the exact seed SQL.

**Tests:** `pip install -r requirements-dev.txt && SENTINEL_DEMO_MODE=1 pytest tests/`

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    SentinelReg                          │
│      Streamlit UI (Investigation / Dashboard / SAR)     │
└──────────────────────┬──────────────────────────────────┘
                       │
              ┌────────▼────────┐
              │ Cortex Analyst  │  ← Text-to-SQL, called directly via
              │  (REST API)     │    the /api/v2/cortex/analyst/message
              └────────┬────────┘    endpoint (no Cortex Agent hop —
                       │              that's blocked on trial accounts)
          ┌────────────┼───────────────┐
          ▼            ▼               ▼
  ┌──────────────┐ ┌──────────────┐ ┌──────────────────┐
  │ Transactions │ │ Regulatory   │ │ Snowflake ML     │
  │ Accounts     │ │ Docs Chunks  │ │ Risk Scorer      │
  │ Alerts       │ │ (RBI/FATF/   │ │ (Gradient        │
  │              │ │ Basel/FinCEN)│ │ Boosting)        │
  └──────────────┘ └──────────────┘ └──────┬───────────┘
                                             │
                                     ┌───────▼──────────┐
                                     │ ML_RISK_FEATURES │
                                     │ (COMPUTED_RISK_  │
                                     │  SCORE)          │
                                     └───────────────────┘
```

Both the transactional/risk tables and the regulatory text chunks live in the
same Cortex Analyst semantic model (`semantic_model/aml_risk_model.yaml`), so
one Text-to-SQL call can answer either kind of question.

---

## Project Structure

```
coco-cli/
├── AGENTS.md                     # Project instructions for the CoCo CLI agent
├── .coco/skills/                 # CoCo CLI Agent Skills scoped to this project
│   ├── investigate-aml-account/SKILL.md
│   ├── generate-sar-report/SKILL.md
│   └── score-fraud-risk/SKILL.md
├── setup/                        # Snowflake infrastructure setup (run 01 → 05 in order)
│   ├── 01_setup_db.sql           # Database, schema, warehouse, roles
│   ├── 02_create_tables.sql      # AML transactions, accounts, alerts, ML features
│   ├── 03_load_synthetic_data.sql# Synthetic AML scenario data (6 fraud typologies)
│   ├── 04_cortex_search.sql      # Regulatory doc chunks (Cortex Search commented out — needs paid account)
│   └── 05_create_agent.sql       # Optional: Cortex Agent object (not used by the app — see note below)
├── semantic_model/
│   └── aml_risk_model.yaml       # Cortex Analyst semantic model
├── regulatory_docs/               # Human-readable source of the chunks in 04_cortex_search.sql
│   ├── rbi_aml_kyc_directions.md # RBI KYC/AML + FATF + Basel excerpts
│   └── fincen_bsa_aml_manual.md  # FinCEN BSA/AML excerpts
├── ml_pipeline/
│   └── fraud_classifier.py       # Snowpark ML fraud classifier (train/score/explain)
├── app/                           # Streamlit application
│   ├── main.py                   # Entry point, theming, navigation
│   ├── views/                    # (named views/, not pages/ — see AGENTS.md)
│   │   ├── investigation.py      # Natural-language investigation chat (Cortex Analyst)
│   │   ├── risk_dashboard.py     # Risk command center
│   │   └── sar_generator.py      # SAR/STR report generation
│   └── utils/
│       ├── agent_client.py       # Cortex Analyst REST API wrapper
│       ├── db.py                 # Shared Snowpark session + query helper
│       ├── sar_builder.py        # SAR document template engine
│       └── risk_signals.py       # Rule-based fraud pattern detectors
├── LICENSE
├── .env.example
├── requirements.txt
└── README.md
```

---

## Quick Start

### Prerequisites
- A Snowflake account with Cortex AI enabled (`SNOWFLAKE.CORTEX_USER` role), with `ACCOUNTADMIN`
  access for the one-time `setup/01_setup_db.sql` provisioning step
- [CoCo CLI](https://docs.snowflake.com/en/user-guide/cortex-code/cortex-code) installed and
  authenticated against that same account
- Python 3.11+

### Setup

```bash
# 1. Clone this repository
git clone https://github.com/avanishkasar/coco-cli.git
cd coco-cli

# 2. Set environment variables
cp .env.example .env
# Edit .env with your Snowflake credentials (see "Credentials You'll Need" below)

# 3. Provision the Snowflake backend — run 01 through 04 in order
#    (05_create_agent.sql is optional — the app talks to Cortex Analyst
#    directly and doesn't need the Cortex Agent object it creates).
#    Easiest via CoCo CLI, which picks up AGENTS.md and can run these for you:
coco run "execute setup/01_setup_db.sql through setup/04_cortex_search.sql in order against my Snowflake account"

#    ...or directly with SnowSQL:
snowsql -f setup/01_setup_db.sql
snowsql -f setup/02_create_tables.sql
snowsql -f setup/03_load_synthetic_data.sql
snowsql -q "PUT file://semantic_model/aml_risk_model.yaml @sentinel_reg.data.models AUTO_COMPRESS=false;"
snowsql -f setup/04_cortex_search.sql

# 4. (Optional) Train the ML fraud classifier
pip install -r requirements.txt
python ml_pipeline/fraud_classifier.py --mode train
python ml_pipeline/fraud_classifier.py --mode score

# 5. Launch the app
streamlit run app/main.py
```

The three CoCo CLI Agent Skills under `.coco/skills/` (`investigate-aml-account`,
`generate-sar-report`, `score-fraud-risk`) are picked up automatically by CoCo CLI in
this project directory — try `coco "investigate ACC-9823"` from the repo root.

---

## Example Questions You Can Ask

```
💬 "Why was account ACC-9823 flagged for AML?"
💬 "Show me all structuring transactions above ₹49,000 in the last 7 days"
💬 "What does RBI say about velocity-based transaction monitoring?"
💬 "Generate a SAR for alert ALERT-2024-0047"
💬 "Which accounts have unusual round-trip transfer patterns this month?"
💬 "List all customers in the high-risk KYC tier with recent large cash deposits"
💬 "Explain the shell account fan-out on ACC-0009 and what FinCEN says about layering"
💬 "Is Horizon Exports' cash activity consistent with its declared business?"
```

---

## Fraud Typologies Covered

Six distinct, independently detectable AML scenarios are seeded in
`setup/03_load_synthetic_data.sql` and re-implemented in pure Python in
`app/utils/risk_signals.py`, so the same logic that generated the demo data
can also be explained live in the UI:

| Typology | Example account | Detection rule |
|---|---|---|
| **Structuring** | ACC-0006 (Greenleaf Trading) | 3+ cash deposits just under ₹50,000 within 72 hours |
| **Round-Trip Transfer** | ACC-0009 (Nexus Capital) | Funds sent out and ≥80% returned within 8 days |
| **Velocity Burst** | ACC-9823 (Amit Desai) | 5+ outgoing transfers within 2 hours |
| **Cash-Intensive Business** | ACC-0004 (Horizon Exports) | >70% cash ratio inconsistent with declared business |
| **Shell Account Fan-Out** | ACC-0009 → ACC-0012/13/14 | Large inbound wire fanned out same-day to 3+ shell-profile accounts |
| **Clean baseline noise** | ACC-0001, ACC-0003 | No pattern — proves the system doesn't over-flag normal activity |

---

## Built With

- **Snowflake Cortex Analyst** — Natural language to SQL, called directly via its REST API (over both transactional/risk tables and regulatory text)
- **Snowflake Cortex Search** — supported by the architecture but disabled by default (needs `EMBED_TEXT_768`, unavailable on trial accounts); regulatory Q&A runs through Cortex Analyst/SQL instead
- **Snowflake ML** — Supervised fraud classification (XGBoost via Snowpark)
- **Snowflake CoCo CLI** — Agentic workflow automation and skills
- **Streamlit** — Interactive compliance dashboard UI

---

## Regulatory Coverage

| Framework | Documents Indexed |
|---|---|
| RBI (India) | Master Direction on KYC/AML (2023 updated) |
| Basel Committee | AML/CFT Risk Assessment Guidelines |
| FinCEN (US) | BSA/AML Examination Manual |
| FATF | 40 Recommendations Reference |

---

## Credentials You'll Need

Everything runs on Snowflake-hosted models — **no external LLM API key
is required.** You need:

| Variable | Where to get it |
|---|---|
| `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`, `SNOWFLAKE_PASSWORD` | Your Snowflake account (trial or GCC-provided account works). `ACCOUNTADMIN` needed once, to run `setup/01_setup_db.sql`. |
| `SENTINEL_REG_PAT` | A Snowflake [Personal Access Token](https://docs.snowflake.com/en/user-guide/security-access-control-authenticate-personal-access-token) scoped to `SENTINEL_REG_ROLE`, used by `app/utils/agent_client.py` to call the Cortex Analyst REST API. Requires a network policy to be set on your account/user, or PAT auth returns 401. |
| `SENTINEL_REG_HOST` | Your account's Snowflake hostname, e.g. `xy12345.snowflakecomputing.com`. |
| CoCo CLI auth | Run `coco auth login` (or your org's SSO flow) against the same account so `.coco/skills/` and `AGENTS.md` are usable from the CLI. |

Cortex AI (specifically Cortex Analyst) must be **enabled on the account/region** —
this is on by default for most trial and Snowflake-provisioned accounts. Cortex
Search specifically requires `EMBED_TEXT_768`, which trial accounts don't have
access to; this project routes regulatory Q&A through Cortex Analyst/SQL instead
(see `setup/04_cortex_search.sql`), so no Cortex Search entitlement is required.

---

## How This Maps to the Judging Criteria

| Criterion | How SentinelReg addresses it |
|---|---|
| **Real-World Relevance** | Targets an actual, high-stakes GCC workflow — AML/fraud investigation and SAR/STR filing — with citations traceable to real RBI, FATF, Basel and FinCEN text, and filing deadlines computed from real regulatory timelines (7 days FIU-IND, 30/60 days FinCEN). |
| **Technical Execution** | Combines Cortex Analyst (text-to-SQL over both transactional and regulatory data), a Snowpark ML classifier surfaced live in the dashboard, and real-time UI features (auto-refresh, deterministic regulatory search) — plus CoCo CLI Agent Skills (`.coco/skills/`) and an `AGENTS.md` so the CLI itself is a first-class way to operate the system, not just the web UI. |
| **Solution Completeness** | End-to-end: seeded multi-typology synthetic data → detection (rule-based *and* ML) → natural-language investigation → evidence-backed, regulator-ready SAR generation → dashboard for portfolio-level triage — runnable from a clean Snowflake account with five idempotent setup scripts. |

---

*Built for the Snowflake CoCo CLI Hackathon 2026 — GCC Edition.*
