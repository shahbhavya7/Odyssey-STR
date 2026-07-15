"""Prompt-accuracy harness: score the router against a labeled golden set.

Loads a JSON golden set (fresh, held-out tickets with expected labels produced
by a stronger model), runs each ticket through the real route_ticket(), and
reports per-field accuracy, overall exact-match, a by-difficulty breakdown, a
review-flag reliability check, and a list of every mismatch.

Usage:
    python tests/eval/run_eval.py                          # uses golden_set.json
    python tests/eval/run_eval.py tests/eval/golden_set.sample.json
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent          # tests/eval
sys.path.insert(0, str(HERE.parent.parent))     # repo root, so app.* imports work

from app.router_service import route_ticket  # noqa: E402
from app.schema import Category, Priority, Team  # noqa: E402

_VALID = {
    "category": {c.value for c in Category},
    "priority": {p.value for p in Priority},
    "assigned_team": {t.value for t in Team},
}
_FIELDS = ("category", "priority", "assigned_team", "needs_human_review")


def _load(path: Path) -> list[dict]:
    """Read the golden set and fail loudly if any expected label is invalid."""
    data = json.loads(path.read_text(encoding="utf-8"))
    for i, item in enumerate(data):
        exp = item["expected"]
        for field, allowed in _VALID.items():
            if exp[field] not in allowed:
                raise ValueError(
                    f"Item {item.get('id', i)}: expected {field}={exp[field]!r} "
                    f"is not a valid enum value."
                )
    return data


def main() -> None:
    """Run the golden set through the router and print a scorecard."""
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "golden_set.json"
    if not path.exists():
        print(f"Golden set not found: {path}")
        print(f"Generate one with the GPT prompt, or try {HERE / 'golden_set.sample.json'}")
        sys.exit(1)

    items = _load(path)
    total = len(items)
    field_hits = dict.fromkeys(_FIELDS, 0)
    exact_hits = 0
    by_diff: dict[str, list[int]] = defaultdict(lambda: [0, 0])  # diff -> [exact, n]
    review_expected = review_caught = 0
    mismatches: list[str] = []

    print(f"Scoring {total} tickets from {path} ...\n")
    for item in items:
        exp = item["expected"]
        got = route_ticket(item["ticket"])
        diff = item.get("difficulty", "unspecified")

        per_field_ok = {}
        for field in _FIELDS:
            ok = got[field] == exp[field]
            per_field_ok[field] = ok
            if ok:
                field_hits[field] += 1

        all_ok = all(per_field_ok.values())
        exact_hits += all_ok
        by_diff[diff][0] += all_ok
        by_diff[diff][1] += 1

        # Reliability: when a human review is expected, did the model flag it?
        if exp["needs_human_review"]:
            review_expected += 1
            if got["needs_human_review"]:
                review_caught += 1

        if not all_ok:
            wrong = [
                f"{f}: exp {exp[f]!r} != got {got[f]!r}"
                for f in _FIELDS
                if not per_field_ok[f]
            ]
            mismatches.append(
                f"  [{item.get('id', '?')}] ({diff}) {item['ticket'][:60]!r}\n"
                f"        " + "; ".join(wrong)
            )

    def pct(n: int, d: int) -> str:
        return f"{(100 * n / d):5.1f}%" if d else "  n/a"

    print("=" * 60)
    print("PER-FIELD ACCURACY")
    for field in _FIELDS:
        print(f"  {field:<20} {pct(field_hits[field], total)}  ({field_hits[field]}/{total})")
    print(f"\n  EXACT MATCH (all 4)  {pct(exact_hits, total)}  ({exact_hits}/{total})")

    print("\nBY DIFFICULTY (exact match)")
    for diff in sorted(by_diff):
        hit, n = by_diff[diff]
        print(f"  {diff:<20} {pct(hit, n)}  ({hit}/{n})")

    print("\nREVIEW-FLAG RELIABILITY")
    print(
        f"  flagged when expected {pct(review_caught, review_expected)}  "
        f"({review_caught}/{review_expected})"
    )

    if mismatches:
        print("\n" + "=" * 60)
        print(f"MISMATCHES ({len(mismatches)})")
        print("\n".join(mismatches))
    print("=" * 60)


if __name__ == "__main__":
    main()
