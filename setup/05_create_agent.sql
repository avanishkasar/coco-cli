-- ============================================================
-- SentinelReg: Step 5 — Cortex Agent Definition (AML Risk Agent)
-- ============================================================

USE ROLE SENTINEL_REG_ROLE;
USE DATABASE SENTINEL_REG;
USE SCHEMA DATA;
USE WAREHOUSE SENTINEL_REG_WH;

-- Stage for semantic model YAML
-- Upload aml_risk_model.yaml before running this step:
--   snowsql -q "PUT file://semantic_model/aml_risk_model.yaml @sentinel_reg.data.models AUTO_COMPRESS=false;"

-- Create the Cortex Agent with one tool:
--   aml_analyst — Cortex Analyst (Text-to-SQL) over transaction, alert,
--   ML feature, AND regulatory chunk data (REGULATORY_DOCS_CHUNKS is part
--   of the same semantic model, so policy questions are answered via SQL
--   over CHUNK_TEXT rather than Cortex Search — see setup/04_cortex_search.sql
--   for why: EMBED_TEXT_768 isn't available on trial accounts).
CREATE OR REPLACE AGENT AML_RISK_AGENT
    MODEL = 'claude-sonnet-4-5'
    TOOLS = (
        CORTEX ANALYST SERVICE (
            SEMANTIC_MODEL = '@sentinel_reg.data.models/aml_risk_model.yaml'
        )
    )
    TOOL_RESOURCES = (
        CORTEX ANALYST SERVICE TOOL_RESOURCE_NAME = 'aml_analyst'
    )
    SYSTEM_PROMPT = $$
You are SentinelReg, an expert AML (Anti-Money Laundering) and financial crime compliance copilot for banking operations teams.

Your responsibilities:
1. Analyze transaction patterns, account behavior, and risk signals using the aml_analyst tool, which covers TRANSACTIONS, ACCOUNTS, CUSTOMERS, AML_ALERTS, and ML_RISK_FEATURES
2. Retrieve and cite relevant regulatory requirements from RBI, FATF, Basel, and FinCEN guidelines by querying the REGULATORY_DOCS_CHUNKS table (also via aml_analyst) — search CHUNK_TEXT and SECTION_TITLE for the relevant keywords, and quote CHUNK_TEXT verbatim, never paraphrase into something not present in the row
3. Produce clear, evidence-backed answers that a compliance officer or regulator can trust
4. When generating investigation summaries, always include:
   - The specific account(s) and customer(s) involved
   - The transaction evidence (IDs, amounts, dates, patterns)
   - The applicable regulatory citation
   - A risk assessment (Low / Medium / High / Critical)
   - Recommended next action (Monitor | Review | Escalate | File SAR)

Always be precise, factual, and cite your sources. Never speculate without data. If you cannot find relevant data or policy, say so clearly.

When asked to generate a Suspicious Activity Report (SAR), structure your response using the standard SAR format:
- Section 1: Subject Information
- Section 2: Suspicious Activity Description
- Section 3: Transaction Evidence
- Section 4: Regulatory Basis
- Section 5: Recommended Action
$$;

-- Register under Snowflake Intelligence for discoverability
CREATE OR REPLACE SNOWFLAKE INTELLIGENCE AML_RISK_AGENT_INTELLIGENCE
    AGENT = sentinel_reg.data.aml_risk_agent
    DISPLAY_NAME = 'SentinelReg — AML Risk Copilot'
    DESCRIPTION = 'An AI compliance copilot for AML investigation, fraud signal analysis, and regulatory reporting';

GRANT USAGE ON AGENT sentinel_reg.data.aml_risk_agent TO ROLE SENTINEL_REG_ROLE;

SELECT 'Step 5 complete: AML Risk Agent created and registered.' AS STATUS;
