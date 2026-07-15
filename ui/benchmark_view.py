"""Streamlit "Benchmarks" page: read a benchmark results file and visualize it.

Reading only running models happens in eval/run_benchmark.py (there's a small
smoke-test button that shells out to it). Degrades gracefully when no results exist.
"""

from __future__ import annotations

import html
import json
import subprocess
import sys
from pathlib import Path

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


# --- HTML renderers (no pandas / no Arrow avoids the pyarrow rerun segfault) ---

_HILITE = "background:rgba(182,92,255,0.30);border-radius:6px;"
_CELL = "padding:8px 12px;border-bottom:1px solid rgba(255,255,255,0.08);font-size:0.9rem;"
_HEAD = ("padding:8px 12px;border-bottom:1px solid rgba(255,255,255,0.18);"
         "font-size:0.72rem;font-weight:700;text-transform:uppercase;color:#B4A9C4;text-align:right;")


def _html_table(headers: list[str], rows: list[list[str]], best_cols: dict[int, int]) -> str:
    """Return an HTML table. best_cols maps column index -> row index to highlight."""
    ths = f"<th style='{_HEAD}text-align:left;'>{html.escape(headers[0])}</th>" + "".join(
        f"<th style='{_HEAD}'>{html.escape(h)}</th>" for h in headers[1:]
    )
    trs = ""
    for r_idx, row in enumerate(rows):
        tds = f"<td style='{_CELL}color:#F5F0FB;font-weight:600;'>{html.escape(str(row[0]))}</td>"
        for c_idx, val in enumerate(row[1:], start=1):
            hi = _HILITE if best_cols.get(c_idx) == r_idx else ""
            tds += (f"<td style='{_CELL}text-align:right;font-variant-numeric:tabular-nums;"
                    f"color:#DDE1EA;'><span style='{hi}padding:2px 6px;'>{html.escape(str(val))}</span></td>")
        trs += f"<tr>{tds}</tr>"
    return (
        f"<div style='overflow-x:auto;'><table style='width:100%;border-collapse:collapse;'>"
        f"<thead><tr>{ths}</tr></thead><tbody>{trs}</tbody></table></div>"
    )


def _leaderboard_rows(summary: dict, configs: list[dict]) -> list[dict]:
    rows = []
    for cfg in configs:
        s = summary.get("per_model", {}).get(cfg["name"], {})
        if s and s.get("n", 0) > 0:
            rows.append({"name": cfg["name"], **{k: s.get(k, 0) for k, _, _ in _LEADERBOARD_COLS}})
    return rows


def _render_leaderboard(rows: list[dict]) -> None:
    st.markdown("#### Leaderboard")
    if not rows:
        st.warning("No model produced results in this run.")
        return
    headers = ["Model"] + [h for _, h, _ in _LEADERBOARD_COLS]
    best_cols: dict[int, int] = {}
    for c_idx, (key, _, higher) in enumerate(_LEADERBOARD_COLS, start=1):
        if len(rows) > 1:
            vals = [r[key] for r in rows]
            best = (max if higher else min)(vals)
            best_cols[c_idx] = vals.index(best)
    table_rows = [
        [r["name"]] + [
            f"{r[key]:.0f}" if key == "avg_latency_ms" else f"{r[key]:.1f}"
            for key, _, _ in _LEADERBOARD_COLS
        ]
        for r in rows
    ]
    st.markdown(_html_table(headers, table_rows, best_cols), unsafe_allow_html=True)


def _render_bar_chart(rows: list[dict]) -> None:
    st.markdown("#### Exact-match accuracy")
    if not rows:
        return
    hues = ["#B65CFF", "#E85BC6", "#34E0A1", "#F5A524", "#FF8FA3", "#37CBB0"]
    bars = ""
    for i, r in enumerate(sorted(rows, key=lambda x: x["exact_pct"], reverse=True)):
        pct = max(0.0, min(100.0, float(r["exact_pct"])))
        hue = hues[i % len(hues)]
        bars += (
            "<div style='margin:8px 0;'>"
            "<div style='display:flex;justify-content:space-between;font-size:0.85rem;"
            f"color:#B4A9C4;margin-bottom:4px;'><span>{html.escape(r['name'])}</span>"
            f"<span style='color:{hue};font-weight:700;'>{pct:.1f}%</span></div>"
            "<div style='background:rgba(255,255,255,0.08);border-radius:999px;height:10px;'>"
            f"<div style='width:{pct:.1f}%;height:10px;background:{hue};border-radius:999px;"
            f"box-shadow:0 0 10px {hue}66;'></div></div></div>"
        )
    st.markdown(bars, unsafe_allow_html=True)


def _render_variance(summary: dict, configs: list[dict]) -> None:
    st.markdown("#### Consistency vs. accuracy (the honest view)")
    st.caption(
        "Exact-match % with ± the run-to-run standard deviation, plus how often all "
        "runs agreed. High accuracy with low variance is what you want."
    )
    rows = []
    for cfg in configs:
        s = summary.get("per_model", {}).get(cfg["name"], {})
        if s and s.get("n", 0) > 0:
            rows.append([
                cfg["name"],
                f"{s.get('exact_pct', 0):.1f} ± {s.get('exact_stddev', 0):.1f}",
                f"{s.get('consistency_pct', 0):.1f}",
                f"{s.get('valid_json_pct', 0):.1f}",
            ])
    if rows:
        st.markdown(
            _html_table(["Model", "Exact %", "Consistency %", "Valid JSON %"], rows, {}),
            unsafe_allow_html=True,
        )


def _render_breakdowns(summary: dict, configs: list[dict]) -> None:
    st.markdown("#### Where each model wins or fails")
    dim = st.radio("Break down by", ["difficulty", "tag"], horizontal=True)
    key = "by_difficulty" if dim == "difficulty" else "by_tag"
    ran = [c for c in configs if summary.get("per_model", {}).get(c["name"], {}).get("n", 0) > 0]
    groups: set[str] = set()
    for cfg in ran:
        groups.update(summary["per_model"][cfg["name"]].get(key, {}).keys())
    if not groups:
        st.caption("No breakdown available.")
        return
    headers = [dim] + [c["name"] for c in ran]
    rows = []
    for group in sorted(groups):
        row = [group]
        for cfg in ran:
            vals = summary["per_model"][cfg["name"]].get(key, {}).get(group)
            row.append(f"{vals['exact_pct']:.1f}" if vals else "—")
        rows.append(row)
    st.caption("Exact-match % per group (higher is better).")
    st.markdown(_html_table(headers, rows, {}), unsafe_allow_html=True)


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
    if cols[0].button("Run quick smoke test", help="5 tickets, 1 run may take a minute"):
        with st.spinner("Running 5-ticket smoke test… this may take a minute."):
            ok, out = _run_smoke_test()
        if ok:
            st.success("Smoke test complete showing the latest results.")
        else:
            st.error("Smoke test failed:")
            st.code(out)
        st.rerun()
    cols[1].caption(
        "Full run: `python eval/run_benchmark.py` (all models, 3× can take a while "
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

    rows = _leaderboard_rows(summary, configs)
    _render_leaderboard(rows)
    _render_bar_chart(rows)
    _render_variance(summary, configs)
    _render_breakdowns(summary, configs)
    _render_worst_misses(payload)
