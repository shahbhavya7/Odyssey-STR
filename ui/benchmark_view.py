"""Streamlit "Benchmarks" page: read a benchmark results file and visualize it.

Reading only — running models happens in eval/run_benchmark.py (there's a small
smoke-test button that shells out to it). Degrades gracefully when no results exist.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

from ui.components import stat_cards

ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = ROOT / "eval" / "results"
RUNNER = ROOT / "eval" / "run_benchmark.py"

# Leaderboard columns: (payload key, header, higher-is-better?).
_LEADERBOARD_COLS = [
    ("exact_pct", "Exact %", True),
    ("category_pct", "Category %", True),
    ("team_pct", "Team %", True),
    ("priority_pct", "Priority %", True),
    ("review_pct", "Review %", True),
    ("consistency_pct", "Consistency %", True),
    ("valid_json_pct", "Valid JSON %", True),
    ("avg_latency_ms", "Avg ms", False),
]


def _list_result_files() -> list[Path]:
    """Timestamped result files, newest first (latest.json excluded from the list)."""
    if not RESULTS_DIR.exists():
        return []
    files = [p for p in RESULTS_DIR.glob("*.json") if p.name != "latest.json"]
    return sorted(files, reverse=True)


def _load(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _no_results_notice() -> None:
    st.info(
        "No benchmark results yet. Generate them first:\n\n"
        "```bash\npython eval/run_benchmark.py --limit 5 --repeats 1   # quick\n"
        "python eval/run_benchmark.py                              # full\n```"
    )


def _run_smoke_test() -> tuple[bool, str]:
    """Shell out to the runner for a 5-ticket / 1x smoke test. Returns (ok, output)."""
    try:
        proc = subprocess.run(
            [sys.executable, str(RUNNER), "--limit", "5", "--repeats", "1"],
            cwd=str(ROOT), capture_output=True, text=True, timeout=600,
        )
        return proc.returncode == 0, (proc.stdout + proc.stderr)[-3000:]
    except Exception as err:  # noqa: BLE001 - report cleanly to the UI
        return False, f"{type(err).__name__}: {err}"


def _leaderboard_df(summary: dict, configs: list[dict]) -> pd.DataFrame:
    rows = []
    for cfg in configs:
        s = summary.get("per_model", {}).get(cfg["name"], {})
        if not s or s.get("n", 0) == 0:
            continue
        rows.append({"Model": cfg["name"], **{h: s.get(k, 0) for k, h, _ in _LEADERBOARD_COLS}})
    return pd.DataFrame(rows)


def _render_leaderboard(df: pd.DataFrame) -> None:
    st.markdown("#### Leaderboard")
    if df.empty:
        st.warning("No model produced results in this run.")
        return
    styler = df.style.format({h: "{:.1f}" for _, h, hib in _LEADERBOARD_COLS if h != "Avg ms"})
    styler = styler.format({"Avg ms": "{:.0f}"})
    # Highlight the best cell per column (max for accuracy, min for latency).
    for _, header, higher_is_better in _LEADERBOARD_COLS:
        if len(df) > 1 and header in df.columns:
            if higher_is_better:
                styler = styler.highlight_max(subset=[header], color="rgba(182,92,255,0.35)")
            else:
                styler = styler.highlight_min(subset=[header], color="rgba(182,92,255,0.35)")
    st.dataframe(styler, width="stretch", hide_index=True)


def _render_bar_chart(df: pd.DataFrame) -> None:
    st.markdown("#### Accuracy by metric")
    if df.empty:
        return
    metric_cols = ["Exact %", "Category %", "Team %", "Priority %", "Review %"]
    chart_df = df.set_index("Model")[metric_cols]
    # Transpose so metrics are on the x-axis and each model is a colored series.
    st.bar_chart(chart_df.T, width="stretch")


def _render_variance(summary: dict, configs: list[dict]) -> None:
    st.markdown("#### Consistency vs. accuracy (the honest view)")
    st.caption(
        "Exact-match % with ± the run-to-run standard deviation, plus how often all "
        "runs agreed. High accuracy with low variance is what you want."
    )
    rows = []
    for cfg in configs:
        s = summary.get("per_model", {}).get(cfg["name"], {})
        if not s or s.get("n", 0) == 0:
            continue
        rows.append({
            "Model": cfg["name"],
            "Exact %": f"{s.get('exact_pct', 0):.1f} ± {s.get('exact_stddev', 0):.1f}",
            "Consistency %": f"{s.get('consistency_pct', 0):.1f}",
            "Valid JSON %": f"{s.get('valid_json_pct', 0):.1f}",
        })
    if rows:
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)


def _render_breakdowns(summary: dict, configs: list[dict]) -> None:
    st.markdown("#### Where each model wins or fails")
    dim = st.radio("Break down by", ["difficulty", "tag"], horizontal=True)
    key = "by_difficulty" if dim == "difficulty" else "by_tag"
    table: dict[str, dict[str, float]] = {}
    for cfg in configs:
        s = summary.get("per_model", {}).get(cfg["name"], {})
        breakdown = s.get(key, {}) if s else {}
        for group, vals in breakdown.items():
            table.setdefault(group, {})[cfg["name"]] = vals.get("exact_pct", 0)
    if not table:
        st.caption("No breakdown available.")
        return
    df = pd.DataFrame(table).T.sort_index()
    df.index.name = dim
    st.caption("Exact-match % per group (higher is better).")
    st.dataframe(df.style.format("{:.1f}"), width="stretch")


def _render_worst_misses(payload: dict) -> None:
    st.markdown("#### Worst misses (top model)")
    summary = payload.get("summary", {}).get("per_model", {})
    if not summary:
        return
    ran = [c for c in payload.get("metadata", {}).get("configs", [])
           if summary.get(c["name"], {}).get("n", 0) > 0]
    if not ran:
        return
    top = max(ran, key=lambda c: summary[c["name"]].get("exact_pct", 0))
    st.caption(f"Tickets the best model (**{top['name']}**) still got wrong.")
    seen: set[str] = set()
    misses = []
    for rec in payload.get("records", []):
        if rec["model"] != top["name"] or rec.get("exact_correct"):
            continue
        if rec["id"] in seen:
            continue
        seen.add(rec["id"])
        misses.append(rec)
    if not misses:
        st.success(f"{top['name']} got every ticket exactly right. 🎉")
        return
    for rec in misses:
        exp, pred = rec.get("expected", {}), rec.get("pred", {})
        with st.expander(f"#{rec['id']} · {rec.get('difficulty')} · {', '.join(rec.get('tags') or [])}"):
            st.write(f"**Message:** {rec.get('text', '')}")
            c1, c2 = st.columns(2)
            c1.markdown("**Expected**")
            c1.json(exp)
            c2.markdown("**Predicted**")
            c2.json(pred)


def page_benchmarks() -> None:
    """The Benchmarks page."""
    st.subheader("📊 Model Benchmarks")

    # --- smoke-test button (running the full suite is via the CLI script) ---
    cols = st.columns([1, 3])
    if cols[0].button("Run quick smoke test", help="5 tickets, 1 run — may take a minute"):
        with st.spinner("Running 5-ticket smoke test… this may take a minute."):
            ok, out = _run_smoke_test()
        if ok:
            st.success("Smoke test complete — showing the latest results.")
        else:
            st.error("Smoke test failed:")
            st.code(out)
        st.rerun()
    cols[1].caption(
        "Full run: `python eval/run_benchmark.py` (all models, 3× — can take a while "
        "and, for OpenAI configs, cost money)."
    )

    files = _list_result_files()
    latest = RESULTS_DIR / "latest.json"
    options = (["latest.json"] if latest.exists() else []) + [f.name for f in files]
    if not options:
        _no_results_notice()
        return

    chosen = st.selectbox("Results file", options, index=0)
    path = latest if chosen == "latest.json" else (RESULTS_DIR / chosen)
    payload = _load(path)
    if not payload:
        st.error("Could not read that results file.")
        return

    meta = payload.get("metadata", {})
    configs = meta.get("configs", [])
    summary = payload.get("summary", {})

    stat_cards([
        ("Dataset", str(meta.get("dataset_size", "—")), "#F5F0FB"),
        ("Prompt", str(meta.get("prompt_version", "—")), "#B65CFF"),
        ("Repeats", str(meta.get("repeats", "—")), "#34E0A1"),
        ("Models", str(len(configs)), "#E85BC6"),
        ("Run at", str(meta.get("timestamp", "—")).replace("T", " "), "#F5A524"),
    ])
    if meta.get("skipped"):
        st.caption("Skipped: " + ", ".join(
            f"{s['name']} ({s.get('reason', '')})" for s in meta["skipped"]
        ))

    df = _leaderboard_df(summary, configs)
    _render_leaderboard(df)
    _render_bar_chart(df)
    _render_variance(summary, configs)
    _render_breakdowns(summary, configs)
    _render_worst_misses(payload)
