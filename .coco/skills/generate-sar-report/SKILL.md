---
name: generate-sar-report
title: Generate a Suspicious Activity Report (SAR/STR)
summary: Turn a confirmed AML alert plus investigation notes into an audit-ready SAR document in the FIU-IND/FinCEN structure.
description: >
  Use when the user asks to draft, generate, or file a SAR/STR for a specific
  alert or account (e.g. "generate a SAR for ALERT-2024-0047", "draft an STR
  for ACC-0006"). Triggers on keywords: SAR, STR, suspicious activity report,
  file a report, draft a report.
type: community
tools: [cortex-analyst, snowpark]
---

# Generate a Suspicious Activity Report

## Workflow

1. **Resolve the alert.** Require an `ALERT_ID` (or resolve one open,
   non-SAR-filed alert from an `ACCOUNT_ID`/`CUSTOMER_ID`). Refuse to proceed
   if the alert is already `SAR_FILED = TRUE` — say so and stop.
2. **Assemble the record set**: `AML_ALERTS` row, joined `CUSTOMERS` row, and
   up to 15 related `TRANSACTIONS` (prefer the IDs in `AML_ALERTS.TRANSACTION_IDS`
   if populated, else the account's most recent transactions).
3. **Render the six-section SAR** used by this project (mirrors
   `app/utils/sar_builder.py::build_sar_markdown`):
   1. Reporting Entity Information
   2. Subject Information (incl. PEP / sanctions status, KYC tier)
   3. Suspicious Activity Description (alert type, severity, trigger rule,
      free-text summary of findings)
   4. Transaction Evidence (markdown table)
   5. Regulatory Basis (cite RBI Master Direction Para 15 STR timelines for
      India, or FinCEN Ch. 4 SAR timelines for US filings, matching the
      customer's jurisdiction)
   6. Recommended Action (mandatory: file within the regulator's deadline;
      conditional: freeze account, EDD, law-enforcement coordination)
4. **State the filing deadline explicitly** — 7 working days for FIU-IND STRs
   (RBI Para 15), 30 days for FinCEN SARs (60 if no suspect identified) — and
   compute the actual due date from `ALERT_DATE`.
5. Remind the user: the subject must never be tipped off about the filing
   (RBI Para 15.5 / BSA confidentiality provisions).

## Common mistakes

- Never invent a SAR reference number that collides with an existing
  `SAR_REFERENCE`; use the app's `SAR-YYYYMMDD-NNN` convention.
- Don't skip Section 4 (Transaction Evidence) even if the user only asked for
  a "quick" SAR — an unsupported SAR is not audit-ready and defeats the
  point of the tool.
- Don't mark `SAR_FILED = TRUE` in the database yourself; that's a
  human-confirmed action in the Streamlit SAR Generator page, not an
  automatic side effect of drafting text.
