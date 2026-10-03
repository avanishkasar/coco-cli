# SentinelReg: reading script

Read each paragraph out loud. The line in brackets after a paragraph tells you what to do on screen, so do it, then keep reading.

Start with the Overview page open.

---

Hello everyone, this is SentinelReg, an assistant that helps banks catch money laundering and fraud. Banks in India must report any suspicious activity to the government within seven days, and today analysts do this by jumping between many tools and typing long reports by hand. SentinelReg puts everything in one place, and it runs fully on Snowflake using Snowflake's own AI.

[Stay on the Overview page. Move the mouse slowly over the top numbers.]

This is the home page. At the top you can see how many alerts are open, how many are critical, and how much money is under review. Each alert also has a timer that counts the days left to file the report, and the seven day rule is read straight from the RBI rules, so nothing is typed in by hand.

[Wait 3 seconds, then scroll down to the Priority queue and point at the red "overdue" tags.]

Here is something special. We had five separate alerts that looked unrelated, but SentinelReg joined the money trail and found that four of them are part of one single network. So the analyst can file one strong report instead of four weak ones.

[Wait 3 seconds, then scroll to the red box about the connected network and point at the graph.]

Now let us open Alert Triage, where the analyst makes the decisions. This is the list of alerts, sorted so the most serious one is first. I will open the critical one where money went out and almost the same amount came back.

[Click "Alert Triage" in the left menu. Wait 3 seconds. In "Open case" choose ALERT-2024-0043.]

Here you see why it was flagged, the exact transactions, and the days left to file. The analyst picks a decision, writes a short note, and saves it. This saves straight into Snowflake, so the AI suggests but the human always decides.

[Change the Disposition, type this note: Checked the source of funds, escalating. Wait 2 seconds, then click "Save decision".]

Behind this list is a rule engine that checks five kinds of suspicious patterns again and again. It also shows any pattern that no alert has covered yet, so nothing slips through. Next to it we use a machine learning model in Snowflake that gives every account a risk score, with simple reasons for the score, so it is never a black box.

[Wait 3 seconds, click the "Detection engine" tab, wait 3 seconds, then click the "ML risk model" tab.]

Now the fun part, we can just ask questions in plain English. I will ask what the RBI says about the reporting time, and the answer comes back word for word from the rule book, with the exact clause number. Every rule we show comes from a real clause stored in our database, so the system can never make up a law.

[Click "Investigation Copilot". Wait 3 seconds. Click the suggestion "What does RBI say about suspicious transaction reporting timelines?"]

Now let me ask about data. Snowflake Cortex Analyst turns my question into a database query, runs it inside Snowflake, and shows me the answer. I can open the query and see exactly what it did, so everything can be checked, and the data never leaves Snowflake.

[Wait 3 seconds. Type: Why was account ACC-9823 flagged for AML? and press Enter. Wait 5 seconds, then click "Generated SQL" to open it.]

Let me show the customer view and the money trail. On this page we see everything about one customer in one place, like their risk level, their accounts, and their alerts. Then the network page draws the money flow as a map, so you can see the shell companies and the suspicious transfers in red.

[Click "Entity 360", choose Nexus Capital Advisory, wait 4 seconds, click the "Fund flow" tab. Then click "Network Intelligence" and wait 4 seconds.]

Now the most useful part, the report. When the analyst clicks here, the report is filled with the customer details, the transactions and the correct rules from the rule book. Then Snowflake AI writes the story of what happened in a few seconds, and our safety check removes any rule that is not in our database.

[Click "SAR Generator". Wait 3 seconds. Open "Regulatory basis". Then click "Draft with Cortex AI" and wait until the green message shows.]

This is our big difference, because the AI can write, but it cannot invent a law. With one click we now get a ready PDF and a full evidence package with a fingerprint, so the officer can prove nothing was changed. After filing, the alert closes and the report number is saved back in Snowflake.

[Scroll down, click "Generate audit-ready SAR", wait 4 seconds, click "PDF report". Then tick the box and click "Confirm SAR filed".]

Finally, the audit trail. Every decision, question and filing is saved here with who did it and when, and each line is locked to the one before it, so if anyone edits the history the page shows a broken chain. This is what an auditor asks for first, and we give it by default.

[Click "Audit Trail". Wait 3 seconds. Point at the green "Chain verified" message and the list of events.]

One more thing, this project also comes with CoCo CLI skills, so the same work can be done from the command line. It has twenty five automated tests, and it has a demo mode so it keeps working even when the Snowflake trial ends. So in short, SentinelReg finds the risk, answers in plain English with proof, writes the report in minutes, and keeps a trail nobody can change. Thank you.

[Click "Overview" to end on the home page. Wait 3 seconds, then stop the recording.]

---

Before you record: open the live link, refresh the page, and check the left side says "Snowflake · live". Say the word "synthetic" once if someone asks about the data, because the data is made up for the demo.
