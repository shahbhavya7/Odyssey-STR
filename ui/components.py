"""Reusable render helpers: colored badges, a confidence bar, and the result card.

Pure presentation — these take a plain dict (a TicketOut from the API) and emit
styled HTML via st.markdown. No API or business logic here.
"""

import html

import streamlit as st

# Priority -> (background, text) colors.
PRIORITY_COLORS: dict[str, tuple[str, str]] = {
    "High": ("#dc2626", "#ffffff"),
    "Medium": ("#d97706", "#ffffff"),
    "Low": ("#16a34a", "#ffffff"),
}

# Each of the 7 teams gets a distinct accent.
TEAM_COLORS: dict[str, str] = {
    "Billing Team": "#0d9488",
    "Account Management": "#4f46e5",
    "Customer Support": "#475569",
    "Product": "#9333ea",
    "Frontend / UI-UX": "#db2777",
    "Backend / API": "#2563eb",
    "DevOps / Infrastructure": "#ea580c",
}


def _pill(text: str, bg: str, fg: str = "#ffffff") -> str:
    """Return HTML for a small rounded colored pill."""
    return (
        f"<span style='background:{bg};color:{fg};padding:3px 10px;"
        f"border-radius:999px;font-size:0.8rem;font-weight:600;"
        f"white-space:nowrap;'>{html.escape(text)}</span>"
    )


def priority_badge(priority: str) -> str:
    """HTML pill for a priority, colored red/amber/green."""
    bg, fg = PRIORITY_COLORS.get(priority, ("#6b7280", "#ffffff"))
    return _pill(f"{priority} priority", bg, fg)


def team_badge(team: str) -> str:
    """HTML pill for the assigned team, in that team's accent color."""
    return _pill(team, TEAM_COLORS.get(team, "#6b7280"))


def review_badge(flag: bool) -> str:
    """HTML pill indicating whether a human review is needed."""
    if flag:
        return _pill("⚠ Needs review", "#b45309")
    return _pill("✓ Auto-routed", "#15803d")


def _confidence_html(conf: float) -> str:
    """HTML for a 0-100% confidence bar, colored by band."""
    pct = max(0.0, min(1.0, float(conf))) * 100
    color = "#dc2626" if conf < 0.4 else "#d97706" if conf < 0.7 else "#16a34a"
    return (
        "<div style='margin:6px 0;'>"
        "<div style='font-size:0.8rem;color:#6b7280;margin-bottom:2px;'>"
        f"Confidence · {pct:.0f}%</div>"
        "<div style='background:#e5e7eb;border-radius:6px;height:10px;width:100%;'>"
        f"<div style='background:{color};width:{pct:.0f}%;height:10px;"
        "border-radius:6px;'></div></div></div>"
    )


def confidence_bar(conf: float) -> None:
    """Render a standalone confidence bar."""
    st.markdown(_confidence_html(conf), unsafe_allow_html=True)


def result_card(ticket: dict) -> None:
    """Render the hero triage card for one routed ticket."""
    category = html.escape(str(ticket.get("category", "—")))
    reasoning = html.escape(str(ticket.get("reasoning", "")))
    review = bool(ticket.get("needs_human_review"))

    banner = ""
    if review:
        banner = (
            "<div style='background:#fef3c7;border:1px solid #f59e0b;color:#92400e;"
            "padding:8px 12px;border-radius:8px;margin:10px 0;font-weight:600;'>"
            "⚠ Needs human review — routed with low confidence.</div>"
        )

    footer = (
        "<div style='color:#9ca3af;font-size:0.75rem;margin-top:12px;"
        "border-top:1px solid #e5e7eb;padding-top:8px;'>"
        f"#{ticket.get('id', '—')} · {html.escape(str(ticket.get('engine', '—')))} · "
        f"prompt {html.escape(str(ticket.get('prompt_version', '—')))} · "
        f"{ticket.get('processing_ms', '—')} ms · "
        f"{html.escape(str(ticket.get('created_at', '—')))}</div>"
    )

    card = (
        "<div style='border:1px solid #e5e7eb;border-radius:14px;padding:18px 20px;"
        "box-shadow:0 1px 3px rgba(0,0,0,0.06);background:var(--background-color,#fff);'>"
        "<div style='display:flex;align-items:center;justify-content:space-between;"
        "gap:12px;flex-wrap:wrap;'>"
        f"<div style='font-size:1.35rem;font-weight:700;'>{category}</div>"
        f"<div>{priority_badge(str(ticket.get('priority', '—')))}</div></div>"
        "<div style='margin-top:10px;display:flex;gap:8px;align-items:center;"
        "flex-wrap:wrap;'>"
        f"{team_badge(str(ticket.get('assigned_team', '—')))}"
        f"{review_badge(review)}</div>"
        f"{_confidence_html(ticket.get('confidence', 0.0))}"
        f"{banner}"
        "<div style='border-left:3px solid #cbd5e1;padding:6px 12px;margin:10px 0;"
        f"color:#374151;font-style:italic;'>“{reasoning}”</div>"
        f"{footer}</div>"
    )
    st.markdown(card, unsafe_allow_html=True)
