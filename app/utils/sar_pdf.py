"""
Regulator-ready PDF rendering of a SAR (fpdf2, core fonts only).

Core PDF fonts are Latin-1, so text is transliterated first (₹ → INR, dashes,
arrows, quotes); anything else unrepresentable becomes '?'.
"""

from __future__ import annotations

from datetime import datetime

import pandas as pd
from fpdf import FPDF
from fpdf.enums import XPos, YPos
from fpdf.fonts import FontFace

GREEN = (11, 46, 34)
GREEN_MID = (14, 107, 78)
GOLD = (169, 121, 10)
INK = (22, 36, 30)
MUTED = (91, 107, 98)
LIGHT = (243, 248, 245)
CREAM = (250, 249, 245)

_TRANSLIT = {
    "₹": "INR ", "—": "-", "–": "-", "→": "->", "←": "<-", "≥": ">=", "≤": "<=", "×": "x",
    "’": "'", "‘": "'", "“": '"', "”": '"', "…": "...", "•": "-", "·": "-", "✓": "v", "⚑": "",
    " ": " ", "​": "",
}


def latin1(text) -> str:
    s = "" if text is None else str(text)
    for k, v in _TRANSLIT.items():
        s = s.replace(k, v)
    return s.encode("latin-1", "replace").decode("latin-1")


def _val(v) -> str:
    if v is None:
        return "-"
    try:
        if pd.isna(v):
            return "-"
    except (TypeError, ValueError):
        pass
    return latin1(v) or "-"


def _inr(v) -> str:
    try:
        return f"INR {float(v):,.0f}"
    except (TypeError, ValueError):
        return "-"


def _date(v, with_time=False) -> str:
    ts = pd.to_datetime(v, errors="coerce")
    if pd.isna(ts):
        return _val(v)
    return ts.strftime("%Y-%m-%d %H:%M" if with_time else "%Y-%m-%d")


class _SarPDF(FPDF):
    def __init__(self, sar_ref: str, doc_hash: str):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.sar_ref = latin1(sar_ref)
        self.doc_hash = doc_hash
        self.set_auto_page_break(auto=True, margin=18)
        self.set_margins(16, 16, 16)
        self.set_title(f"SAR {self.sar_ref}")
        self.set_author("SentinelReg")
        self.set_creator("SentinelReg - AML Risk Intelligence Copilot")

    def header(self):
        if self.page_no() == 1:
            return
        self.set_font("Helvetica", "B", 8)
        self.set_text_color(*MUTED)
        self.cell(0, 6, f"SentinelReg  |  SAR {self.sar_ref}  |  CONFIDENTIAL", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_draw_color(*GOLD)
        self.line(16, self.get_y(), 194, self.get_y())
        self.ln(3)

    def footer(self):
        self.set_y(-13)
        self.set_font("Helvetica", "", 7)
        self.set_text_color(*MUTED)
        self.cell(0, 4, f"Integrity hash (SHA-256 of text version): {self.doc_hash}", align="L")
        self.set_y(-9)
        self.cell(0, 4, f"Page {self.page_no()}/{{nb}}  -  Confidential: do not disclose to the subject (tipping-off prohibited)", align="L")

    def section(self, title: str, min_space: float = 40):
        if self.get_y() > 297 - 18 - min_space:
            self.add_page()
        self.ln(3)
        self.set_font("Helvetica", "B", 11.5)
        self.set_text_color(*GREEN)
        self.cell(0, 7, latin1(title), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_draw_color(*GOLD)
        self.set_line_width(0.5)
        self.line(16, self.get_y(), 60, self.get_y())
        self.set_line_width(0.2)
        self.ln(2.5)

    def kv_table(self, rows: list[tuple[str, str]]):
        self.set_font("Helvetica", "", 8.8)
        self.set_text_color(*INK)
        self.set_draw_color(220, 222, 216)
        with self.table(
            col_widths=(55, 123),
            first_row_as_headings=False,
            line_height=5.2,
            text_align=("LEFT", "LEFT"),
            borders_layout="HORIZONTAL_LINES",
        ) as table:
            for k, v in rows:
                row = table.row()
                row.cell(latin1(k), style=FontFace(emphasis="BOLD", color=GREEN))
                row.cell(latin1(v))
        self.ln(1)

    def paragraph(self, text: str, size: float = 9.2, italic: bool = False, color=INK):
        self.set_font("Helvetica", "I" if italic else "", size)
        self.set_text_color(*color)
        self.multi_cell(0, 4.8, latin1(text), new_x=XPos.LMARGIN, new_y=YPos.NEXT)


def build_sar_pdf(data: dict, doc_hash: str) -> bytes:
    alert = data.get("alert", {}) or {}
    customer = data.get("customer", {}) or {}
    txns = data.get("transactions", []) or []
    citations = data.get("citations", []) or []
    clock = data.get("filing_clock") or {}
    regulator = data.get("regulator", "FIU-IND (RBI)")
    report = clock.get("report", "STR")

    pdf = _SarPDF(data.get("sar_ref", "-"), doc_hash)
    pdf.alias_nb_pages()
    pdf.add_page()

    # Title band
    pdf.set_fill_color(*GREEN)
    pdf.rect(0, 0, 210, 34, style="F")
    pdf.set_fill_color(*GOLD)
    pdf.rect(0, 34, 210, 1.2, style="F")
    pdf.set_xy(16, 9)
    pdf.set_text_color(229, 199, 120)
    pdf.set_font("Helvetica", "B", 8)
    pdf.cell(0, 4, "SENTINELREG  -  AML RISK INTELLIGENCE COPILOT", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_x(16)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Times", "B", 19)
    pdf.cell(0, 10, latin1(f"Suspicious Activity Report ({report})"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_x(16)
    pdf.set_font("Helvetica", "", 8.5)
    pdf.set_text_color(220, 232, 225)
    pdf.cell(0, 5, latin1(f"Reference {data.get('sar_ref', '-')}   |   Recipient: {regulator}   |   Status: DRAFT"),
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_y(42)

    due = clock.get("due")
    due_text = _date(due) if due is not None else "-"
    pdf.set_fill_color(*CREAM)
    pdf.set_draw_color(234, 217, 166)
    pdf.set_text_color(*INK)
    pdf.set_font("Helvetica", "B", 9)
    clock_line = (
        f"Filing deadline: {due_text}  ({clock.get('days', '-')}-day window counted from the alert date"
        + (f", per {clock['chunk_id']}" if clock.get("chunk_id") else "") + ")"
    )
    pdf.multi_cell(0, 6, latin1(clock_line), border=1, fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT, padding=(1.5, 3))

    pdf.section("1. Reporting entity")
    pdf.kv_table([
        ("Reporting institution", _val(data.get("institution"))),
        ("Branch / unit", _val(data.get("branch"))),
        ("Reporting officer", _val(data.get("reporting_officer"))),
        ("Filing date", _val(data.get("filing_date"))),
        ("Generated", _val(data.get("generated_at") or datetime.now().strftime("%Y-%m-%d %H:%M:%S"))),
    ])

    pdf.section("2. Subject")
    pdf.kv_table([
        ("Customer ID", _val(customer.get("CUSTOMER_ID"))),
        ("Name / entity", _val(customer.get("FULL_NAME"))),
        ("Entity type", _val(customer.get("ENTITY_TYPE"))),
        ("Country of origin", _val(customer.get("COUNTRY_OF_ORIGIN"))),
        ("KYC risk tier", _val(customer.get("KYC_TIER"))),
        ("PEP", "YES - enhanced due diligence" if customer.get("PEP_FLAG") else "No"),
        ("Sanctions match", "YES" if customer.get("SANCTIONS_FLAG") else "No"),
        ("Occupation", _val(customer.get("OCCUPATION"))),
        ("Last KYC refresh", _val(customer.get("LAST_KYC_REFRESH"))),
    ])

    pdf.section("3. Suspicious activity")
    pdf.kv_table([
        ("Alert ID", _val(alert.get("ALERT_ID"))),
        ("Account", _val(alert.get("ACCOUNT_ID"))),
        ("Typology", _val(alert.get("ALERT_TYPE"))),
        ("Severity", _val(alert.get("ALERT_SEVERITY"))),
        ("Detected", _date(alert.get("ALERT_DATE"), True)),
        ("Total amount", _inr(alert.get("TOTAL_AMOUNT_INR"))),
        ("Trigger rule", _val(alert.get("TRIGGER_RULE"))),
    ])
    pdf.set_font("Helvetica", "B", 9.5)
    pdf.set_text_color(*GREEN)
    pdf.cell(0, 6, "Narrative", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.paragraph(data.get("investigation_notes") or "No narrative provided.")
    pdf.paragraph(f"Narrative source: {data.get('narrative_source', 'Analyst')}", size=7.5, italic=True, color=MUTED)

    pdf.section("4. Transaction evidence")
    if txns:
        pdf.set_font("Helvetica", "", 7.4)
        pdf.set_text_color(*INK)
        with pdf.table(
            col_widths=(30, 24, 24, 18, 20, 20, 42),
            line_height=4.2,
            text_align=("LEFT", "LEFT", "RIGHT", "LEFT", "LEFT", "LEFT", "LEFT"),
            headings_style=FontFace(emphasis="BOLD", color=(255, 255, 255), fill_color=GREEN_MID),
            borders_layout="HORIZONTAL_LINES",
        ) as table:
            head = table.row()
            for h in ("Transaction", "Date & time", "Amount", "Type", "Channel", "Counterparty", "Narration"):
                head.cell(h)
            for t in txns[:25]:
                row = table.row()
                row.cell(_val(t.get("TRANSACTION_ID")))
                row.cell(_date(t.get("TRANSACTION_DATE"), True))
                row.cell(_inr(t.get("AMOUNT_INR")))
                row.cell(_val(t.get("TRANSACTION_TYPE")))
                row.cell(_val(t.get("CHANNEL")))
                row.cell(_val(t.get("COUNTERPARTY_ACCOUNT")))
                row.cell(_val(t.get("NARRATION")))
    else:
        pdf.paragraph("No transactions retrieved.")

    pdf.section("5. Regulatory basis (verbatim from REGULATORY_DOCS_CHUNKS)", min_space=70)
    if citations:
        for c in citations:
            if pdf.get_y() > 235:
                pdf.add_page()
            pdf.set_font("Helvetica", "B", 9)
            pdf.set_text_color(*GREEN)
            pdf.multi_cell(0, 5, latin1(f"[{c.get('CHUNK_ID')}] {c.get('DOC_TYPE', '')} {c.get('SECTION_NUMBER', '')} - "
                                        f"{c.get('SECTION_TITLE', '')}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.set_font("Helvetica", "I", 7.5)
            pdf.set_text_color(*MUTED)
            pdf.multi_cell(0, 4, latin1(f"{c.get('DOC_NAME', '')} - {c.get('JURISDICTION', '')} - effective "
                                        f"{c.get('EFFECTIVE_DATE', '')}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.set_fill_color(*LIGHT)
            pdf.set_font("Helvetica", "", 8.6)
            pdf.set_text_color(*INK)
            pdf.multi_cell(0, 4.6, latin1(str(c.get("CHUNK_TEXT", "")).strip()), fill=True,
                           new_x=XPos.LMARGIN, new_y=YPos.NEXT, padding=(1.5, 2.5))
            pdf.ln(2)
    else:
        pdf.paragraph("No regulatory clauses attached.")

    pdf.section("6. Recommended action")
    actions = [
        (f"File {report} with {regulator} by {due_text}", "Mandatory"),
        ("Do not inform the subject of this filing", "Mandatory"),
        ("Escalate to Senior Compliance Officer / MLRO", "Recommended"),
        ("Review account restrictions pending investigation", "Recommended"),
        ("Retain alert, evidence and disposition records", "Mandatory"),
    ]
    pdf.kv_table([(p, a) for a, p in actions])

    pdf.ln(4)
    if pdf.get_y() > 255:
        pdf.add_page()
    pdf.set_draw_color(*MUTED)
    y = pdf.get_y()
    pdf.line(16, y + 12, 80, y + 12)
    pdf.line(120, y + 12, 194, y + 12)
    pdf.set_y(y + 13)
    pdf.set_font("Helvetica", "", 7.5)
    pdf.set_text_color(*MUTED)
    pdf.cell(104, 4, latin1(f"Reporting officer: {data.get('reporting_officer', '')}"))
    pdf.cell(0, 4, "Principal Officer / MLRO approval", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    return bytes(pdf.output())
