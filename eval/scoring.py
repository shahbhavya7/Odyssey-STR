"""Scoring for the benchmark harness: compare a prediction to the ground truth.

Multi-issue tickets are scored by the **set** of (category) and (team) across issues,
so order doesn't matter and a single-issue ticket is just a one-element set. Everything
here is pure functions over plain dicts — no model calls, no DB.
"""

from __future__ import annotations

import math
from statistics import pstdev

# Metric keys that are boolean per (ticket, run) and averaged into percentages.
BOOL_METRICS = (
    "is_ticket_correct",
    "category_set_correct",
    "team_set_correct",
    "priority_correct",
    "primary_team_correct",
    "review_flag_correct",
    "exact_correct",
    "valid_json",
)


def _cat_set(issues: list[dict]) -> frozenset[str]:
    return frozenset(str(i.get("category")) for i in (issues or []))


def _team_set(issues: list[dict]) -> frozenset[str]:
    return frozenset(str(i.get("assigned_team")) for i in (issues or []))


def prediction_signature(pred: dict) -> tuple:
    """A hashable fingerprint of a prediction, for run-to-run consistency checks."""
    return (
        bool(pred.get("is_ticket")),
        tuple(sorted(_cat_set(pred.get("issues")))),
        tuple(sorted(_team_set(pred.get("issues")))),
        pred.get("priority"),
        pred.get("primary_team"),
        bool(pred.get("needs_human_review")),
    )


def score_one(pred: dict, expected: dict) -> dict:
    """Score one prediction against its expected label. Returns booleans + metadata.

    `pred` is a route_ticket() output dict; `expected` is a benchmark_set item's
    `expected` block (issues there carry category + assigned_team, no per-issue priority).
    """
    is_ticket_correct = bool(pred.get("is_ticket")) == bool(expected.get("is_ticket"))
    category_set_correct = _cat_set(pred.get("issues")) == _cat_set(expected.get("issues"))
    team_set_correct = _team_set(pred.get("issues")) == _team_set(expected.get("issues"))
    priority_correct = (pred.get("priority") or None) == (expected.get("priority") or None)
    primary_team_correct = (
        (pred.get("primary_team") or None) == (expected.get("primary_team") or None)
    )
    review_flag_correct = (
        bool(pred.get("needs_human_review")) == bool(expected.get("needs_human_review"))
    )
    # valid_json = the model produced schema-valid output (no fallback was triggered).
    valid_json = pred.get("error") is None
    fallback = pred.get("engine") == "fallback"

    exact_correct = all(
        (
            is_ticket_correct,
            category_set_correct,
            team_set_correct,
            priority_correct,
            primary_team_correct,
            review_flag_correct,
        )
    )
    return {
        "is_ticket_correct": is_ticket_correct,
        "category_set_correct": category_set_correct,
        "team_set_correct": team_set_correct,
        "priority_correct": priority_correct,
        "primary_team_correct": primary_team_correct,
        "review_flag_correct": review_flag_correct,
        "exact_correct": exact_correct,
        "valid_json": valid_json,
        "fallback": fallback,
        "processing_ms": int(pred.get("processing_ms") or 0),
    }


def _pct(values: list[bool]) -> float:
    """Percentage of True in a list of bools (0.0 if empty)."""
    return round(100.0 * sum(1 for v in values if v) / len(values), 1) if values else 0.0


def _breakdown(records: list[dict], key: str) -> dict:
    """exact_correct % + n, grouped by a scalar field (e.g. 'difficulty')."""
    groups: dict[str, list[dict]] = {}
    for rec in records:
        groups.setdefault(str(rec.get(key)), []).append(rec)
    return {
        name: {"exact_pct": _pct([r["exact_correct"] for r in rs]), "n": len(rs)}
        for name, rs in sorted(groups.items())
    }


def _tag_breakdown(records: list[dict]) -> dict:
    """exact_correct % + n per tag (a record contributes to each of its tags)."""
    groups: dict[str, list[dict]] = {}
    for rec in records:
        for tag in rec.get("tags") or []:
            groups.setdefault(str(tag), []).append(rec)
    return {
        tag: {"exact_pct": _pct([r["exact_correct"] for r in rs]), "n": len(rs)}
        for tag, rs in sorted(groups.items())
    }


def aggregate_model(records: list[dict], repeats: int) -> dict:
    """Aggregate all (ticket, run) records for ONE model into a summary block.

    Consistency = fraction of tickets where all runs produced the same prediction
    signature. exact_stddev = population stddev of the per-run exact_correct rates
    (how much the "perfect routing" score wobbles run to run).
    """
    if not records:
        return {"n": 0}

    summary: dict = {"n": len(records)}
    summary["exact_pct"] = _pct([r["exact_correct"] for r in records])
    summary["category_pct"] = _pct([r["category_set_correct"] for r in records])
    summary["team_pct"] = _pct([r["team_set_correct"] for r in records])
    summary["priority_pct"] = _pct([r["priority_correct"] for r in records])
    summary["primary_team_pct"] = _pct([r["primary_team_correct"] for r in records])
    summary["review_pct"] = _pct([r["review_flag_correct"] for r in records])
    summary["is_ticket_pct"] = _pct([r["is_ticket_correct"] for r in records])
    summary["valid_json_pct"] = _pct([r["valid_json"] for r in records])

    latencies = [r["processing_ms"] for r in records]
    summary["avg_latency_ms"] = round(sum(latencies) / len(latencies)) if latencies else 0

    # Consistency across runs, per ticket.
    by_ticket: dict[str, list[dict]] = {}
    for rec in records:
        by_ticket.setdefault(rec["id"], []).append(rec)
    consistent = 0
    for runs in by_ticket.values():
        sigs = {r["signature"] for r in runs}
        if len(sigs) == 1:
            consistent += 1
    summary["consistency_pct"] = _pct([True] * consistent + [False] * (len(by_ticket) - consistent))
    summary["n_tickets"] = len(by_ticket)

    # Variance of the exact metric across the R runs.
    per_run_exact: list[float] = []
    for run_idx in range(1, repeats + 1):
        run_recs = [r for r in records if r["run"] == run_idx]
        if run_recs:
            per_run_exact.append(sum(1 for r in run_recs if r["exact_correct"]) / len(run_recs))
    summary["exact_stddev"] = round(100.0 * pstdev(per_run_exact), 1) if len(per_run_exact) > 1 else 0.0

    summary["by_difficulty"] = _breakdown(records, "difficulty")
    summary["by_tag"] = _tag_breakdown(records)
    return summary


def build_summary(records: list[dict], configs: list[dict], repeats: int) -> dict:
    """Per-model aggregates for the whole run (records already carry model + signature)."""
    per_model: dict[str, dict] = {}
    for cfg in configs:
        name = cfg["name"]
        model_recs = [r for r in records if r["model"] == name]
        per_model[name] = aggregate_model(model_recs, repeats)
    return {"per_model": per_model}


def is_finite_number(x: object) -> bool:
    """Guard used by the UI when rendering aggregates."""
    return isinstance(x, (int, float)) and math.isfinite(x)
