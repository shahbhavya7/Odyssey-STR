"""Smart Ticket Router — Streamlit UI.

A thin dining room over the API kitchen: this app only calls the HTTP API and
renders the results. It never touches the database or the routing logic directly.
"""

import os
import sys

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
from ui.components import TEAM_COLORS, result_card  # noqa: E402

st.set_page_config(page_title="Smart Ticket Router", page_icon="🎫", layout="wide")

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


def render_health() -> bool:
    """Show a connection indicator in the sidebar. Returns True if the API is up."""
    try:
        health = get_health()
    except ApiError:
        st.sidebar.error("🔴 API offline — start it with\n`uvicorn app.api:app --port 8000`")
        return False
    db_note = "" if health.get("db_ok") else " · ⚠ DB down"
    st.sidebar.success(
        f"🟢 API connected · {health.get('provider')}:{health.get('model')}{db_note}"
    )
    return True


def offline_banner() -> None:
    """Full-width banner shown on a page when the API is unreachable."""
    st.error(
        "The API is offline. Start it in another terminal:\n\n"
        "`uvicorn app.api:app --reload --port 8000`\n\n"
        "then reload this page."
    )


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
    """Show counts by priority, % needing review, and total time."""
    total = len(results)
    highs = sum(r["priority"] == "High" for r in results)
    meds = sum(r["priority"] == "Medium" for r in results)
    lows = sum(r["priority"] == "Low" for r in results)
    review = sum(bool(r["needs_human_review"]) for r in results)
    ms = sum(int(r.get("processing_ms") or 0) for r in results)
    c = st.columns(5)
    c[0].metric("Tickets", total)
    c[1].metric("🔴 High", highs)
    c[2].metric("🟠 Medium", meds)
    c[3].metric("🟢 Low", lows)
    c[4].metric("Needs review", f"{(100 * review / total):.0f}%" if total else "0%")
    st.caption(f"Total routing time: {ms:,} ms ({ms / 1000:.1f} s)")


def page_batch() -> None:
    """Route many tickets at once — the effortless 20-ticket demo."""
    st.subheader("Batch Demo")
    st.caption("Paste one ticket per line, or upload a .txt/.csv (one per line / first column).")

    pasted = st.text_area("Tickets (one per line)", height=160)
    uploaded = st.file_uploader("…or upload a file", type=["txt", "csv"])

    lines: list[str] = []
    if uploaded is not None:
        raw = uploaded.getvalue().decode("utf-8", errors="ignore")
        for line in raw.splitlines():
            cell = line.split(",")[0].strip() if uploaded.name.endswith(".csv") else line.strip()
            if cell:
                lines.append(cell)
    elif pasted.strip():
        lines = [ln.strip() for ln in pasted.splitlines() if ln.strip()]

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
        df = pd.DataFrame(
            [
                {
                    "id": r["id"],
                    "ticket": r["raw_ticket"][:60],
                    "category": r["category"],
                    "priority": f"{PRIORITY_DOT.get(r['priority'], '')} {r['priority']}",
                    "team": r["assigned_team"],
                    "confidence": round(r["confidence"], 2),
                    "review": "⚠" if r["needs_human_review"] else "",
                }
                for r in results
            ]
        )
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
                result_card(t)


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
    st.title("🎫 Smart Ticket Router")
    st.caption("Read any support message → category, priority, team, and a reason — instantly.")

    api_up = render_health()
    pages = {
        "Route a Ticket": page_route,
        "Batch Demo": page_batch,
        "Browse & Search": page_browse,
        "Find by ID": page_find,
    }
    choice = st.sidebar.radio("Navigate", list(pages.keys()))

    if not api_up:
        offline_banner()
        return
    pages[choice]()


if __name__ == "__main__":
    main()
