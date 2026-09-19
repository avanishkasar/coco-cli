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

-- Create the Cortex Agent with two tools:
--   1. aml_analyst — Cortex Analyst (Text-to-SQL) over transaction + alert data
--   2. policy_search — Cortex Search over regulatory documents
CREATE OR REPLACE AGENT AML_RISK_AGENT
    MODEL = 'claude-sonnet-4-5'
    TOOLS = (
        CORTEX ANALYST SERVICE (
            SEMANTIC_MODEL = '@sentinel_reg.data.models/aml_risk_model.yaml'
        ),
        CORTEX SEARCH SERVICE (
            SERVICE = sentinel_reg.data.aml_regulatory_search,
            MAX_RESULTS = 5
        )
    )
    TOOL_RESOURCES = (
        CORTEX ANALYST SERVICE TOOL_RESOURCE_NAME = 'aml_analyst',
        CORTEX SEARCH SERVICE TOOL_RESOURCE_NAME  = 'policy_search'
    )
    SYSTEM_PROMPT = $$
You are SentinelReg, an expert AML (Anti-Money Laundering) and financial crime compliance copilot for banking operations teams.

Your responsibilities:
1. Analyze transaction patterns, account behavior, and risk signals using structured data tools (use the aml_analyst tool for any data queries)
2. Retrieve and cite relevant regulatory requirements from RBI, FATF, Basel, and FinCEN guidelines (use the policy_search tool for any policy questions)
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
