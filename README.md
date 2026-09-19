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
| 🧠 **Dual Intelligence Engine** | Cortex Analyst (Text-to-SQL) + Cortex Search (Regulatory RAG) combined |
| ⚠️ **Real-Time Fraud Signal Detection** | Velocity checks, structuring patterns, round-trip transfers, shell account behavior |
| 📋 **SAR Report Generation** | One-click Suspicious Activity Report as audit-ready Markdown/PDF |
| 🏦 **Regulatory Compliance Grounding** | Every answer cites RBI / FinCEN policy clause |
| 📊 **Risk Command Dashboard** | Live view of high-risk accounts, alert heatmaps, AML typology breakdown |

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    SentinelReg                          │
│         Streamlit UI (Multi-tab Dashboard)              │
└──────────────────────┬──────────────────────────────────┘
                       │
              ┌────────▼────────┐
              │  Cortex Agent   │  ← Natural language orchestrator
              │  (REST API)     │
              └────────┬────────┘
          ┌────────────┼───────────────┐
          ▼            ▼               ▼
  ┌──────────────┐ ┌──────────────┐ ┌──────────────────┐
  │ Cortex       │ │ Cortex       │ │ Snowflake ML     │
  │ Analyst      │ │ Search       │ │ Risk Scorer      │
  │ (Text→SQL)   │ │ (Policy RAG) │ │ (Classification) │
  └──────┬───────┘ └──────┬───────┘ └──────┬───────────┘
         │                │                 │
  ┌──────▼───────┐ ┌──────▼───────┐ ┌──────▼───────────┐
  │ Transactions │ │ RBI AML PDFs │ │ ML Feature       │
  │ Accounts     │ │ Basel Docs   │ │ Store            │
  │ Alerts Table │ │ FinCEN BSA   │ │                  │
  └──────────────┘ └──────────────┘ └──────────────────┘
```

---

## Project Structure

```
sentinel-reg/
├── setup/                      # Snowflake infrastructure setup
│   ├── 01_setup_db.sql         # Database, schema, warehouse, roles
│   ├── 02_create_tables.sql    # AML transactions, accounts, alerts
│   ├── 03_load_synthetic_data.sql  # Synthetic AML scenario data
│   ├── 04_cortex_search.sql    # Regulatory document search service
│   └── 05_create_agent.sql     # Cortex Agent definition
├── semantic_model/             # Cortex Analyst configuration
│   └── aml_risk_model.yaml     # AML-specific semantic model
├── regulatory_docs/            # Regulatory PDF corpus (chunked)
│   ├── rbi_aml_kyc_directions.md
│   └── fincen_bsa_aml_manual.md
├── app/                        # Streamlit application
│   ├── main.py                 # App entry point
│   ├── pages/
│   │   ├── 01_investigation.py # Natural language investigation chat
│   │   ├── 02_risk_dashboard.py# Risk command center dashboard
│   │   └── 03_sar_generator.py # SAR report generation
│   └── utils/
│       ├── agent_client.py     # Cortex Agent API wrapper
│       ├── sar_builder.py      # SAR report template engine
│       └── risk_signals.py     # Fraud pattern detection helpers
├── ml_pipeline/               # Snowflake ML risk scoring
│   └── fraud_classifier.py     # XGBoost classifier via Snowpark ML
├── coco_skills/               # CoCo CLI reusable skills
│   ├── investigate_account.md  # Skill: investigate an account
│   └── generate_sar.md         # Skill: generate SAR from alert
├── .env.example                # Environment variable template
├── requirements.txt            # Python dependencies
└── README.md
```

---

## Quick Start

### Prerequisites
- Snowflake account with Cortex AI enabled (`SNOWFLAKE.CORTEX_USER` role)
- Python 3.11+
- CoCo CLI installed

### Setup

```bash
# 1. Clone this repository
git clone https://github.com/avanishkasar/coco-cli.git
cd coco-cli

# 2. Set environment variables
cp .env.example .env
# Edit .env with your Snowflake credentials

# 3. Run Snowflake setup scripts in order
snowsql -f setup/01_setup_db.sql
snowsql -f setup/02_create_tables.sql
snowsql -f setup/03_load_synthetic_data.sql
snowsql -f setup/04_cortex_search.sql
snowsql -f setup/05_create_agent.sql

# 4. Upload semantic model
snowsql -q "PUT file://semantic_model/aml_risk_model.yaml @sentinel_reg.data.models AUTO_COMPRESS=false;"

# 5. Install Python dependencies
pip install -r requirements.txt

# 6. Launch the app
streamlit run app/main.py
```

---

## Example Questions You Can Ask

```
💬 "Why was account ACC-9823 flagged for AML?"
💬 "Show me all structuring transactions above ₹49,000 in the last 7 days"
💬 "What does RBI say about velocity-based transaction monitoring?"
💬 "Generate a SAR for alert ALERT-2024-0047"
💬 "Which accounts have unusual round-trip transfer patterns this month?"
💬 "List all customers in the high-risk KYC tier with recent large cash deposits"
```

---

## Built With

- **Snowflake Cortex Agents** — Multi-tool AI agent orchestration
- **Snowflake Cortex Analyst** — Natural language to SQL on transaction data
- **Snowflake Cortex Search** — Semantic search over regulatory documents
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

*Built for the Snowflake CoCo CLI GCC Hackathon 2026*
