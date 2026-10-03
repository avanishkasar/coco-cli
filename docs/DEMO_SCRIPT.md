# SentinelReg: demo recording script (about 5 minutes)

**How to use:** Read the **SAY** lines aloud. The **SHOW** line tells you what to have on screen while you read. Rehearse once, record the voice-over first, then play it back and click through the SHOW cues in time with it.

**Before recording**
- Open the deployed Streamlit link in a clean window (Ctrl+Shift+R) at 1440×900 or larger, with browser zoom at 100%.
- The sidebar should show **Snowflake · live**. If it says Demo snapshot, everything still works, but fix the secrets first.
- Type your name in "Signed in as" so the audit trail reads well.
- Keep this tab order ready: Overview, Alert Triage, Investigation Copilot, Network, SAR Generator, Audit Trail.
- Do one dry run, then refresh. Demo-mode changes reset with the browser session.

🏆 = brownie-point line. Say these with emphasis.

---

## 0:00 – 0:30 · Hook and problem

**SHOW:** Overview page, hero banner at the top.

**SAY:**
"Banks and NBFCs in India must file a Suspicious Transaction Report with FIU-IND within **seven days**. Today an analyst jumps between a transaction system, a case tool, the RBI circulars and Word to do it. It is slow and easy to get wrong.

This is **SentinelReg**, a Risk, Fraud and Regulatory Intelligence Copilot. It takes transactions, account records and AML and Basel texts and turns them into **triaged fraud signals, natural-language answers with regulatory evidence, and audit-ready reports**. That is exactly this problem statement."

🏆 "And it runs on Snowflake with Snowflake's own AI: Cortex Analyst, Cortex AI and Snowpark ML."

---

## 0:30 – 1:15 · Overview: priority queue and filing clocks

**SHOW:** Slowly scroll the KPI cards, then the Priority queue. Point at the red "STR overdue" badges.

**SAY:**
"This is the command center. Open alerts, critical alerts, exposure under review, and the **filing clock**. The seven-day RBI window comes straight from the regulation in our corpus, so the app tells the analyst which cases are overdue or due soon.

Alerts are ranked by severity, then by time left."

🏆 "The deadline is not hard-coded. It is read from the regulatory clause. The same logic gives 30 days for FinCEN when you switch regulator."

**SHOW:** Scroll to the red callout "4 of 5 active alerts sit in one connected fund-flow network".

**SAY:**
"This is where it gets interesting. Five separate alerts looked unrelated. SentinelReg connects the transfers and shows that **four of the five are one laundering network**. One SAR on the whole network is far stronger evidence than four separate filings."

---

## 1:15 – 2:00 · Alert Triage (human in the loop)

**SHOW:** Click **Alert Triage**. Show the queue, then pick ALERT-2024-0043 in "Open case".

**SAY:**
"In Alert Triage the analyst reviews each case. Here is a critical round-trip alert. ₹50 lakh goes out and ₹49 lakh comes straight back. The trigger rule, evidence transactions, PEP flag and filing clock are all in one place.

The analyst picks a disposition, adds a note and saves."

**SHOW:** Change Disposition, type a short note ("Verified source of funds request, escalating"), click **Save decision**. A toast appears.

**SAY:**
"That is a real write-back to the `AML_ALERTS` table in Snowflake. The AI proposes and **the human decides**."

🏆 "Human-in-the-loop is built in, and every decision is logged. I'll show that in a minute."

**SHOW:** Click the **Detection engine** tab.

**SAY:**
"Behind the queue is a rules engine for five typologies: structuring, velocity, round-trip, cash-intensive, and fan-out layering. It re-runs live over the transactions and reconciles against existing alerts, so any pattern **no alert covers** shows up as a gap."

**SHOW:** Click the **ML risk model** tab, point at the scatter plot and reason codes.

**SAY:**
"This is the Snowpark ML fraud classifier against the rule-based score. Points above the diagonal are accounts the model rates riskier than the rules do. Each high score gets plain-English **reason codes**, so it is explainable, not a black box."

---

## 2:00 – 3:00 · Investigation Copilot (natural-language Q&A)

**SHOW:** Click **Investigation Copilot**. Click the suggestion "What does RBI say about suspicious transaction reporting timelines?"

**SAY:**
"Now plain English. I ask what RBI says about STR timelines. The answer quotes the clause **verbatim** and cites the source row, RBI-KYC-003: file within seven days, and never tip off the customer."

🏆 "Every regulatory answer traces to a real row in our regulatory table. The system cannot invent a citation."

**SHOW:** Type: `Why was account ACC-9823 flagged for AML?` and press Enter. Then open the **Generated SQL** expander.

**SAY:**
"For data questions, **Cortex Analyst** converts my question into SQL, runs it inside Snowflake, and returns the rows. Here is the SQL it wrote. It is fully transparent and auditable, and the data never leaves Snowflake."

**SHOW:** Type: `List all open CRITICAL alerts with their total amounts`.

**SAY:**
"One chat covers both transactions and regulations, using one semantic model."

---

## 3:00 – 3:30 · Entity 360 and Network (quick)

**SHOW:** Click **Entity 360**. Select Nexus Capital Advisory. Scroll the profile, risk-driver chips, then click the **Fund flow** tab.

**SAY:**
"Entity 360 gives the whole customer on one screen: KYC tier, PEP status, accounts, risk drivers, alerts, and a two-hop fund-flow map."

**SHOW:** Click **Network Intelligence** and let the graph sit for 3 seconds.

**SAY:**
"And here is the network: the shell accounts in red, frozen accounts dashed, and the flagged transfers as red edges. Layering is easy to see once you can see it."

---

## 3:30 – 4:30 · SAR Generator (the headline feature)

**SHOW:** Click **SAR Generator**. Select ALERT-2024-0043. Scroll the evidence dossier and open the **Regulatory basis** expander.

**SAY:**
"Now the report. The dossier is pulled live. Notice the regulatory basis: the clauses for this typology are attached automatically, quoted word for word from the corpus."

**SHOW:** Click **Draft with Cortex AI**. Wait for the green confirmation.

**SAY:**
"Snowflake Cortex drafts the narrative from the facts. It never writes free-form: the prompt carries only the case facts and the allowed clauses, and then a **citation guardrail** deletes any reference that is not in our corpus."

🏆 "This is our key differentiator. The AI can draft, but it cannot fabricate a regulation."

**SHOW:** Scroll down, click **Generate audit-ready SAR**. Show the SHA-256 line and the preview. Click the **PDF report** button.

**SAY:**
"One click gives a regulator-ready PDF, plus an **evidence package** zip with a hash manifest, so an examiner can verify nothing was altered."

**SHOW:** Tick the confirmation box, click **Confirm SAR filed**.

**SAY:**
"Confirming the filing closes the alert and writes the SAR reference back to Snowflake."

---

## 4:30 – 5:00 · Audit trail, architecture, close

**SHOW:** Click **Audit Trail**. Show "Chain verified" and the timeline with your triage and SAR entries.

**SAY:**
"Every decision, copilot query and filing lands in the audit trail: who, when, what. Each entry is **hash-chained** to the one before, so any edit breaks the chain and the page flags it. That answers an examiner's first question."

🏆 "Beyond the UI: the project ships with CoCo CLI skills and an AGENTS.md, so the same workflows run from the CoCo CLI. It has a full automated test suite, and a demo mode so it keeps working even if the Snowflake trial expires."

**SHOW:** Back to **Overview**, hero banner.

**SAY:**
"SentinelReg: triage the signals, ask in plain English, prove it with the regulation, and file in minutes with a tamper-evident trail. Thank you."

---

# Submission deck: slide content

## Slide 1 · Problem Brief
- **Business problem:** AML teams at banks and NBFCs drown in alerts and must file STRs within 7 days (RBI-KYC-003). Evidence, regulation and reporting live in separate tools.
- **Target user:** AML / compliance analyst and the Principal Officer (MLRO) who approves filings.
- **Pain point today:** manual alert-by-alert review, regulations searched by hand, SAR written in Word, no linked view of related alerts, weak audit evidence.
- **How we improve it:** ranked queue with filing clocks, plain-English investigation, network view that links alerts, AI-drafted narrative with verified citations, one-click PDF and evidence package, tamper-evident audit log.
- **Domain:** BFSI, anti-money-laundering and regulatory compliance (RBI, FATF, Basel, FinCEN).

## Slide 2 · Architecture Diagram
Draw this left to right:

```
DATA (Snowflake, SENTINEL_REG.DATA)
  Structured:   CUSTOMERS · ACCOUNTS · TRANSACTIONS · AML_ALERTS · ML_RISK_FEATURES
  Unstructured: RBI / FATF / Basel / FinCEN text -> REGULATORY_DOCS_CHUNKS
        |
INTELLIGENCE
  Rule engine (5 typologies)  ·  Snowpark ML classifier -> COMPUTED_RISK_SCORE
  Cortex Analyst (semantic model YAML -> SQL)  ·  Cortex COMPLETE (SAR narrative)
        |
APP (Streamlit): Overview · Triage · Copilot · Entity 360 · Network · Regulatory Library · SAR · Audit
        |
OUTPUT: triaged alerts · cited answers · PDF + evidence zip · hash-chained AML_AUDIT_LOG
```
- **CoCo CLI skills (in `.coco/skills/`):** `investigate-aml-account`, `generate-sar-report`, `score-fraud-risk`. Each maps to a page: investigation to Copilot and Entity 360, report generation to the SAR Generator, scoring to the ML risk model tab.
- **Modularity:** one data layer (`utils/data.py`) feeds every page, with live Snowflake and offline demo returning identical shapes. Detectors, SAR builder, narrative drafting and PDF are independent modules.

## Slide 3 · Impact Statement
Be honest with judges and label these as estimates.
- **Time saved (estimate, to validate with a pilot):** SAR assembly from hours of copy-paste to minutes, because evidence, citations and filing clock are auto-attached.
- **Accuracy and compliance:** every citation is traced to a source clause, unsupported ones are stripped automatically, and the filing deadline comes from the regulation.
- **Detection:** in the demo, the network view links 4 of 5 active alerts into one scheme, and the rules engine flags uncovered patterns.
- **Scalability:** the compute runs in Snowflake, so it scales with the warehouse. Add typologies by following the documented 5-step checklist in AGENTS.md.
- **Beyond the demo:** plug in real core-banking feeds, add more regulators (a jurisdiction is just new rows and a filing rule), schedule scoring with Snowflake Tasks, and add role-based access for maker-checker approval.

## Additional Slide · Prototype / MVP Brief
- 8-page working app: Overview, Alert Triage, Investigation Copilot, Entity 360, Network Intelligence, Regulatory Library, SAR Generator, Audit Trail.
- Live on Snowflake with Cortex Analyst, Cortex COMPLETE and Snowpark ML. Offline demo mode as a fallback.
- Automated tests cover page renders, the triage-to-SAR flow, audit tamper detection, and the live SQL path.
- **Prototype link:** your Streamlit URL, `https://coco-cli-kfjwzafq5ousz6uqd7r6vc.streamlit.app`
- **Repo:** `https://github.com/avanishkasar/coco-cli`

---

## Brownie points (cheat sheet)
1. Runs on **Snowflake-native AI**: Cortex Analyst, Cortex COMPLETE, Snowpark ML.
2. **Cannot hallucinate a regulation**: citation guardrail.
3. **Human-in-the-loop** with write-back to Snowflake.
4. **Hash-chained audit trail** with tamper detection.
5. **Network view** links alerts into one scheme.
6. **Filing deadlines computed from the corpus** (7 days RBI, 30 days FinCEN).
7. **PDF plus evidence package** with a hash manifest.
8. **CoCo CLI skills + AGENTS.md**, plus an automated test suite.
9. **Demo-mode fallback** if the trial expires.

## Safe-to-say checklist (so nothing is overclaimed)
- Say "synthetic data" once. The data is seeded demo data, and judges will assume that anyway.
- Say "estimated" for any time-saved number.
- Don't claim integration with FIU-IND's portal. The app produces the filing-ready report; the officer submits it.
