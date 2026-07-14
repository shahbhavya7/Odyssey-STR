"""Escalio — Streamlit UI.

A thin dining room over the API kitchen: this app only calls the HTTP API and
renders the results. It never touches the database or the routing logic directly.
"""

import io
import json
import os
import sys
from pathlib import Path

# Ensure the project root is importable when run via `streamlit run ui/app.py`.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from ui.api_client import (  # noqa: E402
    ApiError,
    create_ticket,
    get_health,
    get_ticket,
    list_tickets,
)
from ui.components import (  # noqa: E402
    TEAM_COLORS,
    offline_panel,
    render_hero,
    result_card,
    stat_cards,
    time_saved_panel,
)
from ui.theme import inject_theme  # noqa: E402

st.set_page_config(
    page_title="Escalio",
    page_icon="🧭",
    layout="wide",
    initial_sidebar_state="expanded",
)

CATEGORIES = [
    "Billing & Payments",
    "Account & Access",
    "How-To / Usage",
    "Bug & Outage",
    "Feature Request",
    "General / Other",
]
TEAMS = list(TEAM_COLORS.keys())
PRIORITY_DOT = {"High": "🔴", "Medium": "🟠", "Low": "🟢"}

EXAMPLES = [
    "I was charged twice for Pro this month, refund the duplicate.",
    "The Save button does nothing when I click it.",
    "Your API returns 500 on POST /orders and my totals are wrong.",
    "Your whole site has been down for the last hour.",
    "Please add a dark mode.",
]

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _read_json(path: Path) -> dict | None:
    """Load a small JSON file, returning None if it's missing or unreadable."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _extract_tickets(uploaded, pasted: str) -> list[str]:
    """Turn an upload or pasted text into a clean list of ticket messages.

    A .csv is parsed properly: the 'text' column is used when present, otherwise
    the last column (so an [id, text] file routes the message, not the id). A
    .txt (or pasted text) is one ticket per line. Never raises on a bad file.
    """
    if uploaded is not None:
        raw = uploaded.getvalue().decode("utf-8", errors="ignore")
        if uploaded.name.lower().endswith(".csv"):
            try:
                df = pd.read_csv(io.StringIO(raw))
                col = "text" if "text" in df.columns else df.columns[-1]
                return [str(v).strip() for v in df[col] if str(v).strip()]
            except Exception:  # noqa: BLE001 - fall back to line splitting
                pass
        return [ln.strip() for ln in raw.splitlines() if ln.strip()]
    if pasted.strip():
        return [ln.strip() for ln in pasted.splitlines() if ln.strip()]
    return []


def fetch_health() -> dict | None:
    """Return the /health payload, or None if the API is unreachable."""
    try:
        return get_health()
    except ApiError:
        return None


# --------------------------------------------------------------------------- #
# Pages
# --------------------------------------------------------------------------- #
def page_route() -> None:
    """Route a single ticket and show its triage card."""
    st.subheader("Route a Ticket")
    st.session_state.setdefault("route_text", "")

    st.caption("Try an example:")
    cols = st.columns(len(EXAMPLES))
    for col, ex in zip(cols, EXAMPLES):
        if col.button(ex[:22] + "…", key=f"ex_{ex[:10]}", help=ex):
            st.session_state.route_text = ex
            st.rerun()

    text = st.text_area("Customer message", key="route_text", height=140)
    if st.button("Route Ticket →", type="primary"):
        if not text.strip():
            st.warning("Please enter a ticket message first.")
            return
        try:
            with st.spinner("Routing…"):
                ticket = create_ticket(text)
        except ApiError as err:
            st.error(str(err))
            return
        result_card(ticket)
        with st.expander("View raw JSON"):
            st.json(ticket)


def _summary_strip(results: list[dict]) -> None:
    """Glass stat cards. Counts cover STORED tickets only; rejects shown separately."""
    stored = [r for r in results if r.get("is_ticket") is not False]
    rejected = len(results) - len(stored)
    total = len(stored)
    highs = sum(r.get("priority") == "High" for r in stored)
    meds = sum(r.get("priority") == "Medium" for r in stored)
    lows = sum(r.get("priority") == "Low" for r in stored)
    review = sum(bool(r.get("needs_human_review")) for r in stored)
    ms = sum(int(r.get("processing_ms") or 0) for r in results)
    stat_cards(
        [
            ("Tickets", str(total), "#F5F0FB"),
            ("High", str(highs), "#FF5C72"),
            ("Medium", str(meds), "#F5A524"),
            ("Low", str(lows), "#34E0A1"),
            ("Rejected", str(rejected), "#776B85"),
            ("Needs review", f"{(100 * review / total):.0f}%" if total else "0%", "#B65CFF"),
            ("Total time", f"{ms / 1000:.1f}s", "#E85BC6"),
        ]
    )


def page_batch() -> None:
    """Route many tickets at once — the effortless 20-ticket demo."""
    st.subheader("Batch Demo")
    st.caption(
        "Paste one ticket per line, or upload a .txt / .csv. "
        "For a CSV, the `text` column is used (try data/sample_tickets.csv)."
    )

    time_saved_panel(
        _read_json(DATA_DIR / "manual_baseline.json"),
        _read_json(DATA_DIR / "ai_timing.json"),
    )

    pasted = st.text_area("Tickets (one per line)", height=160)
    uploaded = st.file_uploader("…or upload a file", type=["txt", "csv"])

    lines = _extract_tickets(uploaded, pasted)

    if st.button("Route All", type="primary"):
        if not lines:
            st.warning("Add some tickets first (paste or upload).")
            return
        results: list[dict] = []
        bar = st.progress(0.0, text="Routing…")
        try:
            for i, line in enumerate(lines, start=1):
                results.append(create_ticket(line))
                bar.progress(i / len(lines), text=f"Routed {i}/{len(lines)}")
        except ApiError as err:
            bar.empty()
            st.error(str(err))
            return
        bar.empty()

        _summary_strip(results)
        rows = []
        for r in results:
            if r.get("is_ticket") is False:
                rows.append({
                    "id": "—",
                    "ticket": r["raw_ticket"][:60],
                    "category": "rejected / not stored",
                    "priority": "🚫",
                    "team": "—",
                    "confidence": "—",
                    "review": "",
                })
            else:
                rows.append({
                    "id": r.get("id", "—"),
                    "ticket": r["raw_ticket"][:60],
                    "category": r["category"],
                    "priority": f"{PRIORITY_DOT.get(r['priority'], '')} {r['priority']}",
                    "team": r["assigned_team"],
                    "confidence": round(r["confidence"], 2),
                    "review": "⚠" if r["needs_human_review"] else "",
                })
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True)

        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "Download results as CSV", csv, "routed_tickets.csv", "text/csv"
        )


def page_browse() -> None:
    """Filter and search stored tickets."""
    st.subheader("Browse & Search")
    c = st.columns(4)
    priority = c[0].selectbox("Priority", ["All", "High", "Medium", "Low"])
    team = c[1].selectbox("Team", ["All", *TEAMS])
    category = c[2].selectbox("Category", ["All", *CATEGORIES])
    needs_review = c[3].checkbox("Needs review only")
    q = st.text_input("Search message text")

    if st.button("Apply", type="primary") or "browse_done" in st.session_state:
        st.session_state["browse_done"] = True
        filters = {
            "priority": priority,
            "team": team,
            "category": category,
            "q": q,
            "limit": 100,
        }
        if needs_review:
            filters["needs_review"] = True
        try:
            data = list_tickets(**filters)
        except ApiError as err:
            st.error(str(err))
            return

        active = [f"{k}={v}" for k, v in filters.items() if v not in ("All", "", 100)]
        st.caption(f"{data['count']} result(s)" + (f" · filters: {', '.join(active)}" if active else ""))
        for t in data["items"]:
            with st.expander(f"#{t['id']} · {t['category']} · {t['priority']} · {t['assigned_team']}"):
                result_card(t, embedded=True)


def page_find() -> None:
    """Fetch a single ticket by its id."""
    st.subheader("Find by ID")
    ticket_id = st.number_input("Ticket ID", min_value=1, step=1, value=1)
    if st.button("Fetch", type="primary"):
        try:
            ticket = get_ticket(int(ticket_id))
        except ApiError as err:
            st.error(str(err))
            return
        if ticket is None:
            st.warning(f"No ticket #{int(ticket_id)} found.")
            return
        result_card(ticket)
        with st.expander("View raw JSON"):
            st.json(ticket)


# --------------------------------------------------------------------------- #
# Shell
# --------------------------------------------------------------------------- #
def main() -> None:
    """App shell: header, sidebar nav, and health-gated page routing."""
    inject_theme()
    health = fetch_health()
    render_hero(health)

    st.sidebar.markdown("#### Navigate")
    pages = {
        "Route a Ticket": page_route,
        "Batch Demo": page_batch,
        "Browse & Search": page_browse,
        "Find by ID": page_find,
    }
    choice = st.sidebar.radio(
        "Navigate", list(pages.keys()), label_visibility="collapsed"
    )

    if health is None:
        offline_panel()
        return
    pages[choice]()


if __name__ == "__main__":
    main()
