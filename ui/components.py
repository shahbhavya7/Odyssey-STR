"""Reusable render helpers: hero, glass badges, confidence bar, stat cards, card.

Pure presentation — these take a plain dict (a TicketOut from the API) and emit
styled HTML via st.markdown, using the design tokens defined in ui/theme.py.
"""

import html
from datetime import datetime

import streamlit as st

# Priority -> hue (tuned for dark).
PRIORITY_COLORS: dict[str, str] = {
    "High": "#FF5C72",
    "Medium": "#F5A524",
    "Low": "#34E0A1",
}

# Each team gets a distinct accent, harmonized with the plasma identity.
TEAM_COLORS: dict[str, str] = {
    "Billing Team": "#F5A524",
    "Account Management": "#B08CFF",
    "Customer Support": "#9AA0AE",
    "Product": "#E85BC6",
    "Frontend / UI-UX": "#FF8FA3",
    "Backend / API": "#37CBB0",
    "DevOps / Infrastructure": "#FF7A45",
}

_GLASS = (
    "background:rgba(255,255,255,0.045);"
    "backdrop-filter:blur(22px) saturate(150%);"
    "-webkit-backdrop-filter:blur(22px) saturate(150%);"
    "border:1px solid rgba(255,255,255,0.10);"
    "box-shadow:0 8px 32px rgba(0,0,0,0.45),inset 0 1px 0 rgba(255,255,255,0.08);"
)


def _rgba(hex_color: str, alpha: float) -> str:
    """Convert #RRGGBB to an rgba() string at the given alpha."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def _pill(text: str, hue: str) -> str:
    """Return HTML for a tinted glass pill in the given hue."""
    return (
        f"<span style='background:{_rgba(hue, 0.14)};color:{hue};"
        f"border:1px solid {_rgba(hue, 0.32)};padding:3px 12px;border-radius:999px;"
        f"font-size:0.78rem;font-weight:600;white-space:nowrap;'>"
        f"{html.escape(text)}</span>"
    )


def priority_badge(priority: str) -> str:
    """HTML pill for a priority (rose/amber/emerald)."""
    return _pill(f"{priority} priority", PRIORITY_COLORS.get(priority, "#94A3B8"))


def team_badge(team: str) -> str:
    """HTML pill for the assigned team in that team's accent."""
    return _pill(team, TEAM_COLORS.get(team, "#94A3B8"))


def review_badge(flag: bool) -> str:
    """HTML pill for the review status."""
    return _pill("Needs review", "#F5A524") if flag else _pill("Auto-routed", "#34E0A1")


def _confidence_html(conf: float) -> str:
    """HTML for a thin confidence bar with a glowing colored fill."""
    pct = max(0.0, min(1.0, float(conf))) * 100
    hue = "#FF5C72" if conf < 0.4 else "#F5A524" if conf < 0.7 else "#34E0A1"
    return (
        "<div style='margin:14px 0 4px;'>"
        "<div style='display:flex;justify-content:space-between;font-size:0.78rem;"
        "color:#B4A9C4;margin-bottom:5px;'><span>Confidence</span>"
        f"<span style='font-variant-numeric:tabular-nums;color:{hue};font-weight:600;'>"
        f"{pct:.0f}%</span></div>"
        "<div style='background:rgba(255,255,255,0.08);border-radius:999px;height:7px;'>"
        f"<div style='background:{hue};width:{pct:.0f}%;height:7px;border-radius:999px;"
        f"box-shadow:0 0 10px {_rgba(hue, 0.6)};'></div></div></div>"
    )


def confidence_bar(conf: float) -> None:
    """Render a standalone confidence bar."""
    st.markdown(_confidence_html(conf), unsafe_allow_html=True)


def _status_pill(health: dict | None) -> str:
    """HTML for the live API status pill used in the hero."""
    if health is None:
        dot, text, hue = "#FF5C72", "API offline", "#FF5C72"
    else:
        hue = dot = "#34E0A1"
        text = f"API connected · {health.get('provider')}:{health.get('model')}"
        if not health.get("db_ok"):
            text += " · DB down"
            hue = dot = "#F5A524"
    return (
        f"<span style='display:inline-flex;align-items:center;gap:7px;"
        f"background:{_rgba(hue, 0.12)};border:1px solid {_rgba(hue, 0.30)};"
        f"color:{hue};padding:5px 12px;border-radius:999px;font-size:0.78rem;"
        f"font-weight:600;'>"
        f"<span style='width:7px;height:7px;border-radius:999px;background:{dot};"
        f"box-shadow:0 0 8px {dot};'></span>{html.escape(text)}</span>"
    )


def render_hero(health: dict | None) -> None:
    """Render the compact glass hero with a live status pill."""
    st.markdown(
        f"<div class='glass' style='{_GLASS}border-radius:20px;padding:22px 26px;"
        "margin-bottom:22px;display:flex;justify-content:space-between;"
        "align-items:center;gap:16px;flex-wrap:wrap;'>"
        "<div><div style=\"font-family:'Bricolage Grotesque',sans-serif;font-size:1.6rem;"
        "font-weight:700;letter-spacing:-0.02em;color:#F5F0FB;\">Escalio 🧭</div>"
        "<div style='color:#B4A9C4;font-size:0.95rem;margin-top:2px;'>"
        "Route any support message into category, priority, team, and a reason instantly."
        "</div></div>"
        f"<div>{_status_pill(health)}</div></div>",
        unsafe_allow_html=True,
    )


def offline_panel() -> None:
    """On-theme banner shown when the API is unreachable."""
    st.markdown(
        f"<div class='glass' style='{_GLASS}border-color:{_rgba('#FF5C72', 0.35)};"
        "padding:20px 24px;border-radius:20px;'>"
        "<div style=\"font-family:'Bricolage Grotesque',sans-serif;font-size:1.05rem;"
        "font-weight:600;color:#FF5C72;\">API offline</div>"
        "<div style='color:#B4A9C4;margin-top:6px;'>Start the API in another terminal, "
        "then reload this page:</div>"
        "<div style='margin-top:10px;font-family:monospace;color:#F5F0FB;"
        "background:rgba(255,255,255,0.05);padding:10px 14px;border-radius:12px;'>"
        "uvicorn app.api:app --reload --port 8000</div></div>",
        unsafe_allow_html=True,
    )


def stat_cards(stats: list[tuple[str, str, str]]) -> None:
    """Render a row of small glass stat cards. Each stat = (label, value, hue)."""
    cards = ""
    for label, value, hue in stats:
        cards += (
            f"<div style='flex:1;min-width:120px;{_GLASS}border-radius:16px;"
            "padding:14px 16px;'>"
            f"<div style='color:#B4A9C4;font-size:0.75rem;'>{html.escape(label)}</div>"
            f"<div style=\"font-family:'Bricolage Grotesque',sans-serif;font-size:1.5rem;"
            f"font-weight:700;color:{hue};font-variant-numeric:tabular-nums;"
            f"margin-top:2px;\">{html.escape(value)}</div></div>"
        )
    st.markdown(
        f"<div style='display:flex;gap:12px;flex-wrap:wrap;margin:6px 0 16px;'>{cards}</div>",
        unsafe_allow_html=True,
    )


def time_saved_panel(manual: dict | None, ai: dict | None) -> None:
    """Glass panel comparing manual triage time vs the AI router.

    Reads the two numbers already measured by the baseline/timing scripts. If
    either is missing, shows a friendly "run the scripts" note instead of crashing.
    """
    if not manual or not ai:
        st.markdown(
            f"<div style='{_GLASS}border-radius:16px;padding:16px 18px;margin:6px 0 16px;"
            "color:#B4A9C4;font-size:0.9rem;'>"
            "<strong style='color:#F5F0FB;'>Time Saved</strong> — not measured yet. "
            "Run <code>python scripts/manual_baseline.py</code> and "
            "<code>python scripts/ai_timing.py</code> to populate this.</div>",
            unsafe_allow_html=True,
        )
        return

    manual_s = float(manual.get("avg_seconds_per_ticket", 0) or 0)
    ai_ms = float(ai.get("avg_ms_per_ticket", 0) or 0)
    ai_s = ai_ms / 1000.0
    faster_pct = (100 * (manual_s - ai_s) / manual_s) if manual_s > 0 else 0.0
    mins_saved_100 = (manual_s - ai_s) * 100 / 60.0

    def _stat(label: str, value: str, hue: str) -> str:
        return (
            "<div style='flex:1;min-width:150px;'>"
            f"<div style='color:#B4A9C4;font-size:0.75rem;'>{html.escape(label)}</div>"
            f"<div style=\"font-family:'Bricolage Grotesque',sans-serif;font-size:1.5rem;"
            f"font-weight:700;color:{hue};font-variant-numeric:tabular-nums;"
            f"margin-top:2px;\">{html.escape(value)}</div></div>"
        )

    st.markdown(
        f"<div style='{_GLASS}border-radius:18px;padding:18px 20px;margin:6px 0 16px;'>"
        "<div style=\"font-family:'Bricolage Grotesque',sans-serif;color:#F5F0FB;"
        "font-size:1.05rem;font-weight:700;margin-bottom:12px;\">⏱ Time Saved</div>"
        "<div style='display:flex;gap:16px;flex-wrap:wrap;'>"
        f"{_stat('Manual (human)', f'{manual_s:.0f}s / ticket', '#F5A524')}"
        f"{_stat('AI router', f'{ai_s * 1000:.0f}ms / ticket', '#34E0A1')}"
        f"{_stat('Faster by', f'{faster_pct:.0f}%', '#B65CFF')}"
        f"{_stat('Saved / 100 tickets', f'{mins_saved_100:.0f} min', '#E85BC6')}"
        "</div>"
        "<div style='color:#776B85;font-size:0.72rem;margin-top:12px;'>"
        f"Manual baseline measured over {html.escape(str(manual.get('n', '?')))} tickets; "
        f"AI over {html.escape(str(ai.get('n', '?')))} ({html.escape(str(ai.get('source', '?')))}). "
        "Excludes queueing/hand-off time, so real-world savings are typically higher."
        "</div></div>",
        unsafe_allow_html=True,
    )


def _format_created_at(value: object) -> str:
    """Return an API timestamp in a compact, readable form."""
    text = str(value or "")
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return text or "—"
    return parsed.strftime("%d %b %Y, %H:%M")


def rejected_card(ticket: dict, *, embedded: bool = False) -> None:
    """Render a non-ticket outcome: reasoning ONLY, muted, clearly not stored.

    This is a normal result (not an error), so it stays on-theme and calm — no
    category/priority/team badges, no confidence bar, no id.
    """
    reasoning = html.escape(str(ticket.get("reasoning", "—")))
    raw_ticket = html.escape(str(ticket.get("raw_ticket", "—")))
    container_style = (
        "padding:8px 2px 4px;"
        if embedded
        else f"{_GLASS}border-radius:20px;padding:22px 24px;margin-bottom:12px;opacity:0.92;"
    )
    st.markdown(
        f"<div style='{container_style}overflow-wrap:anywhere;'>"
        "<div style='display:flex;align-items:center;gap:9px;'>"
        "<span style='font-size:1.1rem;'>🚫</span>"
        "<span style=\"font-family:'Bricolage Grotesque',sans-serif;font-size:1.15rem;"
        "font-weight:700;color:#B4A9C4;\">Not a valid ticket</span></div>"
        "<div style='margin-top:14px;padding:13px 15px;background:rgba(255,255,255,0.03);"
        "border:1px solid rgba(255,255,255,0.07);border-radius:12px;'>"
        "<div style='color:#776B85;font-size:0.7rem;font-weight:700;text-transform:uppercase;'>"
        "Message</div>"
        f"<div style='color:#B4A9C4;font-size:0.92rem;line-height:1.5;margin-top:5px;'>{raw_ticket}</div>"
        "</div>"
        "<div style='margin-top:14px;'>"
        "<div style='color:#776B85;font-size:0.7rem;font-weight:700;text-transform:uppercase;'>"
        "Why it was rejected</div>"
        f"<div style='color:#DDE1EA;line-height:1.5;margin-top:5px;'>{reasoning}</div></div>"
        "<div style='margin-top:14px;color:#776B85;font-size:0.75rem;font-style:italic;'>"
        "Not saved to the database.</div></div>",
        unsafe_allow_html=True,
    )


def result_card(ticket: dict, *, embedded: bool = False) -> None:
    """Render a triage outcome. Non-tickets get the muted rejected card."""
    if ticket.get("is_ticket") is False or ticket.get("stored") is False:
        rejected_card(ticket, embedded=embedded)
        return
    category = html.escape(str(ticket.get("category", "—")))
    raw_ticket = html.escape(str(ticket.get("raw_ticket", "—")))
    reasoning = html.escape(str(ticket.get("reasoning", "—")))
    team = html.escape(str(ticket.get("assigned_team", "—")))
    priority = str(ticket.get("priority", "—"))
    review = bool(ticket.get("needs_human_review"))
    confidence = max(0.0, min(1.0, float(ticket.get("confidence", 0.0))))
    confidence_hue = (
        "#FF5C72" if confidence < 0.4 else "#F5A524" if confidence < 0.7 else "#34E0A1"
    )
    container_style = (
        "padding:8px 2px 4px;"
        if embedded
        else f"{_GLASS}border-radius:20px;padding:22px 24px;margin-bottom:12px;"
    )

    review_banner = ""
    if review:
        review_banner = (
            f"<div style='display:flex;align-items:center;gap:9px;background:{_rgba('#F5A524', 0.10)};"
            f"border:1px solid {_rgba('#F5A524', 0.30)};color:#F5A524;"
            "padding:10px 13px;border-radius:10px;margin-top:14px;font-size:0.86rem;"
            "font-weight:600;'>&#9888; Low confidence. Please review this routing.</div>"
        )

    error_banner = ""
    if ticket.get("error"):
        error_banner = (
            f"<div style='color:#FF5C72;font-size:0.8rem;margin-top:10px;'>"
            f"Routing note: {html.escape(str(ticket['error']))}</div>"
        )

    verdict = ""
    if ticket.get("human_verdict"):
        verdict = (
            "<div style='margin-top:12px;color:#34E0A1;font-size:0.82rem;font-weight:600;'>"
            f"Human verdict: {html.escape(str(ticket['human_verdict']))}</div>"
        )

    card = (
        f"<div style='{container_style}overflow-wrap:anywhere;'>"
        "<div style='display:flex;justify-content:space-between;align-items:flex-start;"
        "gap:14px;flex-wrap:wrap;'>"
        "<div><div style='color:#B65CFF;font-size:0.72rem;font-weight:700;"
        "text-transform:uppercase;'>"
        f"Ticket #{html.escape(str(ticket.get('id', '—')))}</div>"
        "<div style=\"font-family:'Bricolage Grotesque',sans-serif;font-size:1.35rem;"
        f"font-weight:700;letter-spacing:0;color:#F5F0FB;margin-top:3px;\">{category}</div></div>"
        "<div style='display:flex;gap:7px;align-items:center;flex-wrap:wrap;'>"
        f"{priority_badge(priority)}{review_badge(review)}</div></div>"
        "<div style='margin-top:16px;padding:13px 15px;background:rgba(255,255,255,0.035);"
        "border:1px solid rgba(255,255,255,0.08);border-radius:12px;'>"
        "<div style='color:#776B85;font-size:0.7rem;font-weight:700;text-transform:uppercase;'>"
        "Customer message</div>"
        f"<div style='color:#F5F0FB;font-size:0.95rem;line-height:1.5;margin-top:5px;'>{raw_ticket}</div>"
        "</div>"
        "<div style='display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));"
        "gap:10px;margin-top:10px;'>"
        "<div style='padding:11px 13px;border:1px solid rgba(255,255,255,0.08);"
        "border-radius:10px;background:rgba(255,255,255,0.025);'>"
        "<div style='color:#776B85;font-size:0.7rem;font-weight:700;text-transform:uppercase;'>"
        "Assigned team</div>"
        f"<div style='color:#F5F0FB;font-weight:600;margin-top:4px;'>{team}</div></div>"
        "<div style='padding:11px 13px;border:1px solid rgba(255,255,255,0.08);"
        "border-radius:10px;background:rgba(255,255,255,0.025);'>"
        "<div style='display:flex;justify-content:space-between;gap:10px;'>"
        "<span style='color:#776B85;font-size:0.7rem;font-weight:700;text-transform:uppercase;'>"
        "Confidence</span>"
        f"<strong style='color:{confidence_hue};font-size:0.82rem;'>{confidence * 100:.0f}%</strong></div>"
        "<div style='height:6px;background:rgba(255,255,255,0.08);border-radius:999px;"
        "margin-top:8px;overflow:hidden;'>"
        f"<div style='height:100%;width:{confidence * 100:.0f}%;background:{confidence_hue};"
        f"border-radius:999px;box-shadow:0 0 9px {_rgba(confidence_hue, 0.5)};'></div></div></div></div>"
        "<div style='margin-top:14px;'>"
        "<div style='color:#776B85;font-size:0.7rem;font-weight:700;text-transform:uppercase;'>"
        "Routing rationale</div>"
        f"<div style='color:#DDE1EA;line-height:1.5;margin-top:5px;'>{reasoning}</div></div>"
        f"{review_banner}{error_banner}{verdict}"
        "<div style='display:flex;gap:8px 18px;flex-wrap:wrap;color:#776B85;"
        "font-size:0.72rem;margin-top:16px;padding-top:11px;"
        "border-top:1px solid rgba(255,255,255,0.08);font-variant-numeric:tabular-nums;'>"
        f"<span>Model&nbsp; {html.escape(str(ticket.get('engine', '—')))}</span>"
        f"<span>Prompt&nbsp; {html.escape(str(ticket.get('prompt_version', '—')))}</span>"
        f"<span>Time&nbsp; {html.escape(str(ticket.get('processing_ms', '—')))} ms</span>"
        f"<span>Created&nbsp; {html.escape(_format_created_at(ticket.get('created_at')))}</span>"
        "</div></div>"
    )
    st.markdown(card, unsafe_allow_html=True)
