"""
Regulatory Library Page — SentinelReg
Keyword retrieval over REGULATORY_DOCS_CHUNKS (no LLM in the loop), the
typology → clause map used for SAR citations, and filing obligations
quoted from the corpus.
"""

import re

import pandas as pd
import streamlit as st

from utils import data, ui
from utils.risk_signals import RULE_CATALOGUE

# (obligation, clause, phrase that must appear verbatim in that clause)
OBLIGATIONS = [
    ("File an STR with FIU-IND", "RBI-KYC-003", "within 7 days of being satisfied that a transaction is suspicious"),
    ("Never tip off the customer", "RBI-KYC-003", "shall not tip off customers about an STR filing"),
    ("File a CTR for cash of Rs. 10 lakh and above", "RBI-KYC-002", "on or before the 15th day of the following month"),
    ("Refresh CDD for high-risk customers", "RBI-KYC-001", "at least once in 2 years for high-risk customers"),
    ("Keep monitoring alerts and dispositions", "RBI-KYC-006", "for a minimum period of 5 years"),
    ("File a SAR with FinCEN (US)", "FINCEN-001", "within 30 days of the date of the initial detection"),
]


def _highlight(text: str, terms: list[str]) -> str:
    out = ui.esc(text)
    for t in sorted(set(terms), key=len, reverse=True):
        if len(t) < 3:
            continue
        out = re.sub(rf"(?i)\b({re.escape(ui.esc(t))}\w*)", r"<mark>\1</mark>", out)
    return out


def render_regulatory_library():
    mode = data.mode()
    chunks = data.regulatory_chunks()
    ui.page_header(
        title="Regulatory Library",
        subtitle="RBI, FATF, Basel and FinCEN clauses — searchable, quotable and the only source SAR citations may use.",
        eyebrow="Regulatory intelligence", eyebrow_icon="menu_book",
        chips=[("library_books", f"{len(chunks)} clauses"),
               ("gavel", f"{chunks['DOC_TYPE'].nunique() if not chunks.empty else 0} regulators")],
        mode=mode,
    )
    if chunks.empty:
        st.info("REGULATORY_DOCS_CHUNKS is empty — run setup/04_cortex_search.sql.")
        return

    t1, t2, t3 = st.tabs([":material/search: Search", ":material/account_tree: Typology map",
                          ":material/schedule: Filing obligations"])
    with t1:
        c1, c2, c3 = st.columns([2.2, 1.4, 1.2])
        query = c1.text_input("Search the corpus", placeholder="e.g. structuring, STR timeline, PEP, layering, CTR…",
                              key="regulatory_search_term")
        docs = c2.multiselect("Regulator", sorted(chunks["DOC_TYPE"].unique()), key="reg_docs")
        juris = c3.multiselect("Jurisdiction", sorted(chunks["JURISDICTION"].unique()), key="reg_juris")
        hits = data.search_regulations(query, doc_types=docs or None, jurisdictions=juris or None)
        terms = data._terms(query) if query else []
        st.caption(f"{len(hits)} clause(s)" + (f" ranked by relevance to “{query}”" if query else ""))
        if hits.empty:
            st.info("No clause matched. Try a broader term.")
        for i, r in enumerate(hits.to_dict("records")):
            ui.render(
                f'<div class="sr-clause" style="animation-delay:{i * 0.04:.2f}s"><div class="sr-clause-head">'
                f'{ui.badge(r["CHUNK_ID"], "dark", dot=False)}'
                f'<span class="sr-clause-title">{ui.esc(r["DOC_TYPE"])} {ui.esc(r["SECTION_NUMBER"])} — '
                f'{ui.esc(r["SECTION_TITLE"])}</span>{ui.badge(r["JURISDICTION"], "neutral", dot=False)}</div>'
                f'<div class="sr-clause-doc">{ui.esc(r["DOC_NAME"])} · effective {ui.esc(r["EFFECTIVE_DATE"])}</div>'
                f'<div class="sr-clause-text">{_highlight(r["CHUNK_TEXT"], terms)}</div></div>'
            )

    with t2:
        ui.section("Typology → clause map", "Clauses automatically attached to a SAR for each alert typology "
                                            "(plus RBI-KYC-003 / FATF-R-002 on every filing)", "account_tree")
        typologies = sorted(set(data.TYPOLOGY_CITATIONS) - {"FAN_OUT"})
        ids = sorted({c for t in typologies for c in data.TYPOLOGY_CITATIONS[t]} | set(data.REPORTING_CITATIONS))
        matrix = pd.DataFrame(
            [[("●" if (cid in data.TYPOLOGY_CITATIONS[t] or cid in data.REPORTING_CITATIONS) else "") for cid in ids]
             for t in typologies], index=typologies, columns=ids,
        )
        st.dataframe(matrix, width="stretch")
        st.caption("Detection rules behind each typology:")
        st.dataframe(pd.DataFrame(RULE_CATALOGUE), hide_index=True, width="stretch")

    with t3:
        ui.section("Filing obligations", "Each line is shown only if its phrase appears verbatim in the cited clause",
                   "schedule")
        by_id = chunks.set_index("CHUNK_ID")
        for title, cid, phrase in OBLIGATIONS:
            if cid not in by_id.index or phrase not in str(by_id.loc[cid, "CHUNK_TEXT"]):
                continue
            ui.render(
                f'<div class="sr-clause"><div class="sr-clause-head">{ui.badge(cid, "dark", dot=False)}'
                f'<span class="sr-clause-title">{ui.esc(title)}</span></div>'
                f'<div class="sr-clause-text">“…<mark>{ui.esc(phrase)}</mark>…”</div></div>'
            )
