---
name: investigate-aml-account
title: Investigate an AML-flagged account
summary: Pull transaction evidence, risk features, and regulatory basis for one account and produce a structured investigation memo.
description: >
  Use when a compliance analyst asks CoCo to look into a specific account or
  customer (e.g. "investigate ACC-9823", "why is this account risky",
  "build me a case file for CUST-006"). Triggers on keywords: investigate,
  look into, case file, why flagged, risk profile, account review.
type: community
tools: [cortex-analyst, cortex-search, snowpark]
---

# Investigate an AML-flagged account

## Workflow

1. **Resolve the subject.** Accept an `ACCOUNT_ID` or `CUSTOMER_ID`. If the user
   gives a name, look it up via `SELECT CUSTOMER_ID, FULL_NAME FROM CUSTOMERS
   WHERE FULL_NAME ILIKE '%<name>%'`.
2. **Pull account + risk context** from `SENTINEL_REG.DATA`:
   - `ACCOUNTS` (balance, status, `RISK_SCORE`)
   - `CUSTOMERS` (KYC_TIER, PEP_FLAG, SANCTIONS_FLAG)
   - `ML_RISK_FEATURES` for the latest `FEATURE_DATE` (velocity, cash ratio,
     structuring count, round-trip flag)
   - `AML_ALERTS` where `ACCOUNT_ID` matches, ordered by `ALERT_DATE DESC`
   - Last 20 rows of `TRANSACTIONS` for the account, ordered by date desc
3. **Ground every finding in regulation.** For each fraud typology present
   (`ALERT_TYPE`), run a Cortex Search query against `AML_REGULATORY_SEARCH`
   for that typology (e.g. "structuring cash deposits threshold") and cite the
   returned `DOC_NAME` + `SECTION_NUMBER`.
4. **Produce the memo** in this exact structure:
   - **Subject** — name, entity type, KYC tier, PEP/sanctions flags
   - **Evidence** — the specific transactions (IDs, dates, amounts) that
     triggered concern, in a markdown table
   - **Pattern Assessment** — which typology this matches and why, in plain
     English a non-technical reviewer can follow
   - **Regulatory Basis** — 1-3 citations from `AML_REGULATORY_SEARCH`
   - **Risk Rating** — Low / Medium / High / Critical, derived from
     `RISK_SCORE` / `COMPUTED_RISK_SCORE` (>0.85 Critical, >0.70 High, >0.50
     Medium, else Low)
   - **Recommended Action** — Monitor / Review / Escalate / File SAR

## Common mistakes

- Do not state a risk score or regulatory citation you did not actually
  retrieve — query first, write second.
- Do not average `RISK_SCORE` (rule-based) and `COMPUTED_RISK_SCORE` (ML
  output) into one number; report both and explain the difference if they
  disagree.
- Do not recommend "File SAR" for LOW/MEDIUM ratings without an open
  `AML_ALERTS` row backing it — that's a compliance overreach, not a
  data-driven finding.
