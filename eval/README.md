# Prompt Evaluation Lab

Turns "our prompt is good" into a number. A labeled set of tickets (each with the
*correct* routing) is run through the real `route_ticket()`, and the output is
scored field-by-field. This is how we measure a prompt change instead of guessing.

## Files

| File | What it is |
|------|------------|
| `run_eval.py` | The scorer. Loads a labeled set, runs each ticket through `route_ticket()`, prints per-field accuracy, overall exact-match, a by-difficulty breakdown, review-flag reliability, and every mismatch. |
| `golden_set.json` | **Dev set** (30 tickets, `G01–G30`). Used to *tune* the prompt — v1.2 was iterated against it, so its score is optimistic. |
| `test_set.json` | **Held-out test set** (40 tickets, `H01–H40`). Never used for tuning, so its score is the honest measure of generalization. |
| `golden_set.sample.json` | A tiny 3-ticket sample for a quick smoke-run. |

Each item:
```json
{
  "id": "G01",
  "difficulty": "easy | edge | hard",
  "ticket": "the customer message",
  "expected": {
    "category": "...", "priority": "...",
    "assigned_team": "...", "needs_human_review": true
  },
  "notes": "why this is the correct routing"
}
```

## Why a dev/test split

Once you tune a prompt against a set, that set's score is no longer honest — you've
fitted to it. So we keep two sets: iterate against the **dev** set, and report the
number from the **held-out test** set, which the prompt has never seen. When the two
scores agree (they do — see below), the improvement is real, not memorized.

## Run it

```bash
source .venv/bin/activate
python eval/run_eval.py                       # dev set (golden_set.json)
python eval/run_eval.py eval/test_set.json    # held-out test set
```

The local model (`qwen2.5:7b`) is not perfectly deterministic even at temperature 0,
so single-ticket results can flip by ±1–2 between runs. Average 2–3 runs before
trusting a small difference.

## Results (qwen2.5:7b)

Prompt iteration, scored on the dev set (exact-match = all four fields correct):

| Version | Change | Exact match |
|---------|--------|-------------|
| v1.1 | baseline | 56.7% |
| v1.2 | churn-threat fix, priority disambiguation, data-loss, non-English few-shot | 70.0% |
| v1.2 + guard | code-level non-English review guard in `router_service` | 76.7% |

Held-out **test set** with v1.2 + guard: **80.0% exact** — category 92.5%, priority
95.0%, assigned_team 87.5%, needs_human_review 92.5%. The test score matching the dev
score (~77–80%) is the signal that v1.2 generalizes rather than overfitting `G01–G30`.

## What the remaining misses are

Not systematic bugs — three known, mostly-irreducible classes:
- **Debatable labels:** security categorization (Account & Access vs Bug/Backend),
  the under-used "General / Other" bucket, and How-To vs Feature ambiguity. The
  "correct" answer is genuinely arguable.
- **English ambiguous/co-equal review:** the code guard covers non-English; English
  "which layer?" cases still depend on the model flagging itself.
- **Run-to-run noise:** ±1–2 tickets from the model's non-determinism.

## Extending the sets

Generate more labeled tickets with a stronger model (GPT) as the grader, following the
v1.2 rubric verbatim, and avoid reusing the few-shot examples in `app/prompts.py` (so
the set stays a real holdout). Append to `test_set.json` to grow the honest measure.
