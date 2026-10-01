"""
Small HTML/CSS component kit shared by every page (styles live in assets/theme.css).

Everything interpolated into HTML goes through esc() — values come from the
database and from analysts, so they are never trusted as markup.
"""

from __future__ import annotations

import base64
import html
from functools import lru_cache
from pathlib import Path

import streamlit as st

ASSETS = Path(__file__).resolve().parent.parent / "assets"
SEVERITY_CLASS = {"CRITICAL": "critical", "HIGH": "high", "MEDIUM": "medium", "LOW": "low"}
STATUS_CLASS = {
    "OPEN": "high",
    "UNDER_REVIEW": "gold",
    "ESCALATED": "critical",
    "CLOSED_FALSE_POSITIVE": "neutral",
    "CLOSED_SAR_FILED": "ok",
}
CLOCK_CLASS = {"OVERDUE": "critical", "DUE_SOON": "high", "ON_TRACK": "ok", "FILED": "ok", "UNKNOWN": "neutral"}


def esc(value) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def render(markup: str) -> None:
    st.markdown(markup, unsafe_allow_html=True)


@lru_cache(maxsize=None)
def asset_text(name: str) -> str:
    return (ASSETS / name).read_text(encoding="utf-8")


@lru_cache(maxsize=None)
def asset_data_uri(name: str) -> str:
    data = base64.b64encode((ASSETS / name).read_bytes()).decode("ascii")
    return f"data:image/svg+xml;base64,{data}"


def inject_theme() -> None:
    render(f"<style>{asset_text('theme.css')}</style>")


def icon(name: str) -> str:
    return f'<span class="msr">{esc(name)}</span>'


def badge(text: str, tone: str = "neutral", dot: bool = True) -> str:
    return f'<span class="sr-badge {esc(tone)}">{"<i></i>" if dot else ""}{esc(text)}</span>'


def severity_badge(severity: str) -> str:
    sev = str(severity or "").upper()
    return badge(sev or "—", SEVERITY_CLASS.get(sev, "neutral"))


def status_badge(status: str) -> str:
    st_ = str(status or "").upper()
    return badge(st_.replace("_", " ").title() or "—", STATUS_CLASS.get(st_, "neutral"), dot=False)


def clock_badge(clock: dict) -> str:
    state = clock.get("state", "UNKNOWN")
    days = clock.get("days_left")
    report = clock.get("report", "STR")
    if state == "FILED":
        text = f"{report} filed"
    elif state == "OVERDUE":
        text = f"{report} overdue {abs(days)}d"
    elif days is None:
        text = "No clock"
    elif days == 0:
        text = f"{report} due today"
    else:
        text = f"{report} due in {days}d"
    return badge(text, CLOCK_CLASS.get(state, "neutral"))


def page_header(title: str, subtitle: str, eyebrow: str, eyebrow_icon: str = "shield", chips: list[tuple[str, str]] | None = None,
                mode: str | None = None) -> None:
    chip_html = ""
    if mode:
        live = mode == "LIVE"
        chip_html += (
            f'<span class="sr-chip {"live" if live else "demo"}">{icon("bolt" if live else "science")}'
            f'{"Live · Snowflake" if live else "Demo snapshot"}</span>'
        )
    for chip_icon, chip_text in chips or []:
        chip_html += f'<span class="sr-chip">{icon(chip_icon)}{esc(chip_text)}</span>'
    render(
        f"""<div class="sr-hero">
  <img class="sr-hero-mark" src="{asset_data_uri('logo.svg')}" alt="" />
  <div class="sr-hero-eyebrow">{icon(eyebrow_icon)}{esc(eyebrow)}</div>
  <div class="sr-hero-title">{esc(title)}</div>
  <div class="sr-hero-sub">{esc(subtitle)}</div>
  {f'<div class="sr-hero-meta">{chip_html}</div>' if chip_html else ''}
</div>"""
    )


def kpi_cards(cards: list[dict]) -> None:
    """cards: {label, value, sub, icon, tone ('' | critical | high | gold), pulse}. Integer values count up."""
    parts = []
    for i, card in enumerate(cards):
        value = card.get("value")
        if isinstance(value, int) and not isinstance(value, bool):
            value_html = f'<span class="sr-count" style="--sr-n:{value}" aria-label="{value}" data-value="{value}"></span>'
        else:
            value_html = esc(value)
        tone = card.get("tone", "")
        pulse = " pulse" if card.get("pulse") else ""
        parts.append(
            f'<div class="sr-kpi {esc(tone)}{pulse}" style="animation-delay:{i * 0.06:.2f}s">'
            f'<div class="sr-kpi-top"><span class="sr-kpi-label">{esc(card.get("label"))}</span>'
            f'<span class="sr-kpi-icon">{icon(card.get("icon", "insights"))}</span></div>'
            f'<div class="sr-kpi-value">{value_html}</div>'
            f'<div class="sr-kpi-sub">{esc(card.get("sub", ""))}</div></div>'
        )
    render(f'<div class="sr-kpi-grid">{"".join(parts)}</div>')


def section(title: str, caption: str | None = None, section_icon: str = "insights") -> None:
    render(
        f'<div class="sr-section">{icon(section_icon)}<div><div class="sr-section-title">{esc(title)}</div>'
        f'{f"<div class=sr-section-sub>{esc(caption)}</div>" if caption else ""}</div></div>'
    )


def callout(title: str, body: str, tone: str = "", callout_icon: str = "lightbulb", body_is_html: bool = False) -> None:
    body_html = body if body_is_html else esc(body)
    render(
        f'<div class="sr-callout {esc(tone)}">{icon(callout_icon)}'
        f'<div class="sr-callout-title">{esc(title)}</div><div class="sr-callout-body">{body_html}</div></div>'
    )


def demo_notice(reason: str | None) -> None:
    callout(
        "Demo snapshot in use",
        "Showing the bundled seed data from setup/03 and setup/04 (identical to a freshly provisioned "
        "Snowflake account). Changes you make here stay in this browser session. "
        + (f"Reason: {reason}" if reason else ""),
        tone="",
        callout_icon="science",
    )


def risk_color(score: float) -> str:
    if score >= 0.85:
        return "#BA1A1A"
    if score >= 0.70:
        return "#C8A24A"
    if score >= 0.50:
        return "#147C5B"
    return "#8FB5A3"


def gauge(score: float) -> str:
    pct = max(0.0, min(1.0, float(score or 0))) * 100
    return f'<div class="sr-gauge"><div style="width:{pct:.0f}%;background:{risk_color(score or 0)}"></div></div>'


def initials(name: str) -> str:
    words = [w for w in str(name or "").replace(".", " ").split() if w[:1].isalnum()]
    return "".join(w[0] for w in words[:2]).upper() or "?"


def style_chart(chart):
    """Apply the SentinelReg look to an Altair chart."""
    return (
        chart.configure_view(strokeWidth=0)
        .configure_axis(
            labelFont="Inter", titleFont="Inter", labelColor="#5B6B62", titleColor="#5B6B62",
            gridColor="#EEF0EC", domainColor="#E6E3DA", tickColor="#E6E3DA", labelFontSize=11, titleFontSize=11,
        )
        .configure_legend(labelFont="Inter", titleFont="Inter", labelColor="#33443C", titleColor="#5B6B62",
                          orient="bottom", symbolType="circle")
        .configure_title(font="Playfair Display", color="#0B2E22")
    )
