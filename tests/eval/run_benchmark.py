"""Benchmark runner: score multiple LLM configs against the labeled benchmark set.

Runs each model config over every ticket REPEATS times (for variance), scores each
prediction, and writes a timestamped results file plus results/latest.json for the UI.
Reuses the live routing pipeline (route_ticket_with) it does NOT fork the prompt and
does NOT write to the tickets database.

Usage:
    python tests/eval/run_benchmark.py                       # full run, all configs, 3x
    python tests/eval/run_benchmark.py --limit 5 --repeats 1 # quick smoke test
    python tests/eval/run_benchmark.py --models "Qwen 14B" "GPT-4o-mini"
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent          # tests/eval
ROOT = HERE.parent.parent                        # repo root
sys.path.insert(0, str(ROOT))

from app.config import settings  # noqa: E402
from app.router_service import route_ticket_with  # noqa: E402
from app.prompts import PROMPT_VERSION  # noqa: E402
from tests.eval.model_configs import (  # noqa: E402
    MODEL_CONFIGS,
    availability_note,
    ollama_available_models,
)
from tests.eval.scoring import build_summary, prediction_signature, score_one  # noqa: E402

DATASET = HERE / "benchmark_set.json"
RESULTS_DIR = HERE / "results"


def _git_short_sha() -> str:
    """Return the current git short SHA, or the prompt version if git is unavailable."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=ROOT, capture_output=True, text=True, timeout=5,
        )
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except Exception:
        pass
    return PROMPT_VERSION


def _compact(pred_or_expected: dict) -> dict:
    """A small, JSON-friendly snapshot used for the worst-misses view."""
    issues = pred_or_expected.get("issues") or []
    return {
        "is_ticket": bool(pred_or_expected.get("is_ticket")),
        "categories": sorted({str(i.get("category")) for i in issues}),
        "teams": sorted({str(i.get("assigned_team")) for i in issues}),
        "priority": pred_or_expected.get("priority"),
        "primary_team": pred_or_expected.get("primary_team"),
        "needs_human_review": bool(pred_or_expected.get("needs_human_review")),
    }


def _load_dataset() -> list[dict]:
    return json.loads(DATASET.read_text(encoding="utf-8"))


def _select_configs(names: list[str] | None) -> list[dict]:
    if not names:
        return list(MODEL_CONFIGS)
    wanted = {n.lower() for n in names}
    return [c for c in MODEL_CONFIGS if c["name"].lower() in wanted]


def run(models: list[str] | None, limit: int | None, repeats: int) -> Path:
    """Run the benchmark and write the results file. Returns the results path."""
    dataset = _load_dataset()
    if limit:
        dataset = dataset[:limit]
    configs = _select_configs(models)
    if not configs:
        print("No matching model configs. Available:",
              ", ".join(c["name"] for c in MODEL_CONFIGS))
        raise SystemExit(1)

    groq_key_present = bool(settings.groq_api_key)
    openai_key_present = bool(settings.openai_api_key)
    ollama_models = ollama_available_models(settings.ollama_base_url)

    records: list[dict] = []
    ran_configs: list[dict] = []
    skipped: list[dict] = []

    print(f"Benchmark · prompt {PROMPT_VERSION} · {len(dataset)} tickets · {repeats}x")
    for cfg in configs:
        note = availability_note(
            cfg,
            groq_key_present=groq_key_present,
            openai_key_present=openai_key_present,
            ollama_models=ollama_models,
        )
        if note:
            print(f"  ⨯ {cfg['name']}: {note}")
            skipped.append({**cfg, "reason": note})
            continue

        print(f"  ▶ {cfg['name']} ({cfg['provider']}:{cfg['model']})")
        ran_configs.append(cfg)
        for item in dataset:
            for run_idx in range(1, repeats + 1):
                try:
                    pred = route_ticket_with(item["text"], cfg["provider"], cfg["model"])
                except Exception as err:  # noqa: BLE001 - a bad call is a miss, never abort
                    pred = {
                        "is_ticket": None, "issues": [], "priority": None,
                        "primary_team": None, "needs_human_review": None,
                        "engine": "fallback", "error": f"{type(err).__name__}: {err}",
                        "processing_ms": 0,
                    }
                metrics = score_one(pred, item["expected"])
                records.append({
                    "model": cfg["name"],
                    "id": item["id"],
                    "run": run_idx,
                    "difficulty": item.get("difficulty"),
                    "tags": item.get("tags") or [],
                    "text": item["text"],
                    "signature": json.dumps(prediction_signature(pred), default=str),
                    "expected": _compact(item["expected"]),
                    "pred": {**_compact(pred), "engine": pred.get("engine")},
                    **metrics,
                })
            done = sum(1 for r in records if r["model"] == cfg["name"]) // repeats
            print(f"    {done}/{len(dataset)} tickets", end="\r")
        print()

    summary = build_summary(records, ran_configs, repeats)
    now = datetime.now()
    metadata = {
        "prompt_version": PROMPT_VERSION,
        "timestamp": now.isoformat(timespec="seconds"),
        "repeats": repeats,
        "dataset_file": str(DATASET.relative_to(ROOT)),
        "dataset_size": len(dataset),
        "configs": ran_configs,
        "skipped": skipped,
        "git": _git_short_sha(),
    }
    payload = {"metadata": metadata, "summary": summary, "records": records}

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = now.strftime("%Y%m%d_%H%M%S")
    out_path = RESULTS_DIR / f"{stamp}__{metadata['git']}.json"
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    (RESULTS_DIR / "latest.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    _print_leaderboard(summary, ran_configs)
    if skipped:
        print("\nSkipped:", ", ".join(f"{s['name']} ({s['reason']})" for s in skipped))
    print(f"\nSaved → {out_path.relative_to(ROOT)}  (and results/latest.json)")
    return out_path


def _print_leaderboard(summary: dict, configs: list[dict]) -> None:
    """Print a compact per-model leaderboard to stdout."""
    print("\n" + "─" * 72)
    print(f"{'Model':<14}{'exact':>7}{'cat':>7}{'team':>7}{'prio':>7}"
          f"{'review':>8}{'consist':>9}{'valid':>7}{'ms':>7}")
    print("─" * 72)
    for cfg in configs:
        s = summary["per_model"].get(cfg["name"], {})
        if not s or s.get("n", 0) == 0:
            continue
        print(f"{cfg['name']:<14}{s['exact_pct']:>6.1f}%{s['category_pct']:>6.1f}%"
              f"{s['team_pct']:>6.1f}%{s['priority_pct']:>6.1f}%{s['review_pct']:>7.1f}%"
              f"{s['consistency_pct']:>8.1f}%{s['valid_json_pct']:>6.1f}%"
              f"{s['avg_latency_ms']:>7}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark LLM configs for Escalio.")
    parser.add_argument("--models", nargs="+", help="subset of config names to run")
    parser.add_argument("--limit", type=int, help="only the first N tickets (smoke test)")
    parser.add_argument("--repeats", type=int, default=3, help="runs per ticket (default 3)")
    args = parser.parse_args()

    if not DATASET.exists():
        print(f"Benchmark set not found: {DATASET}")
        return 1
    run(args.models, args.limit, max(1, args.repeats))
    return 0


if __name__ == "__main__":
    sys.exit(main())
