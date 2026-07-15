# Prompt Evaluation Lab

Turns "our prompt is good" into a number. A labeled set of tickets (each with the
*correct* routing) is run through the real `route_ticket()`, and the output is
scored field-by-field. This is how we measure a prompt change instead of guessing.

## Files

| File | What it is |
|------|------------|
| `run_eval.py` | The scorer. Loads a labeled set, runs each ticket through `route_ticket()`, prints per-field accuracy, overall exact-match, a by-difficulty breakdown, review-flag reliability, and every mismatch. |
| `golden_set.json` | **Dev set** (30 tickets, `G01–G30`). Used to *tune* the prompt v1.2 was iterated against it, so its score is optimistic. |
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

## Multi-issue scoring (v1.4)

Since v1.4 a ticket can hold several issues. The single-label `expected` above scores
the **ticket-level** priority and the **primary** issue's category/team (the flat
back-compat fields), which keeps the existing golden/test sets valid unchanged.

To score multi-issue *extraction* itself, compare the **set** of `(category, team)`
pairs the model produced against an expected set order-independent, so
`{(Billing, Billing Team), (Account & Access, Account Management)}` matches regardless
of which issue came first. The multi-issue tickets in `data/sample_tickets.csv`
(ids 21–23) are the seed for this; their expected sets are:

| id | message (abbrev.) | expected issue set `(category → team)` | ticket priority |
|----|-------------------|----------------------------------------|-----------------|
| 21 | can't log in + double-charged | Account & Access → Account Management ; Billing & Payments → Billing Team | High (billing) |
| 22 | checkout 500s + FAQ typo | Bug & Outage → Backend / API ; Bug & Outage → Frontend / UI-UX | High (backend) |
| 23 | dashboard won't load + wants dark mode | Bug & Outage → DevOps / Infrastructure ; Feature Request → Product | High (outage) |

A future `run_eval.py` flag can load these and report set precision/recall per ticket.

## Why a dev/test split

Once you tune a prompt against a set, that set's score is no longer honest you've
fitted to it. So we keep two sets: iterate against the **dev** set, and report the
number from the **held-out test** set, which the prompt has never seen. When the two
scores agree (they do see below), the improvement is real, not memorized.

## Run it

```bash
source .venv/bin/activate
python tests/eval/run_eval.py                       # dev set (golden_set.json)
python tests/eval/run_eval.py eval/test_set.json    # held-out test set
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

Held-out **test set** with v1.2 + guard: **80.0% exact** category 92.5%, priority
95.0%, assigned_team 87.5%, needs_human_review 92.5%. The test score matching the dev
score (~77–80%) is the signal that v1.2 generalizes rather than overfitting `G01–G30`.

## What the remaining misses are

Not systematic bugs three known, mostly-irreducible classes:
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

---

# Model Benchmark Harness

A separate, richer harness that compares **multiple LLM configs** against a labeled
answer key, runs each **3× for variance**, scores per-field + set-based accuracy, and
renders a comparison view in the Streamlit **📊 Benchmarks** tab.

## 1. The dataset

`eval/benchmark_set.json` 60 hand-reviewed tickets. Each item:

```json
{
  "id": "T24", "text": "...", "difficulty": "hard",
  "tags": ["multi_issue", "billing", "account_access"],
  "expected": {
    "is_ticket": true,
    "issues": [{"category": "...", "assigned_team": "...", "reasoning": "..."}],
    "priority": "High", "primary_team": "Billing Team", "needs_human_review": false
  },
  "label_notes": "why this is the correct routing"
}
```

It is the **ground truth** (already human-reviewed): the labels encode the v1.2/v1.4
rubric business-impact priority, symptom-based bug sub-routing, gibberish/greeting
rejection, non-English review, prompt-injection resistance, and multi-issue extraction
(single, two-, and three-issue cases, plus over-split traps). To extend it, add items
in the same shape and re-verify by hand.

## 2. Run it

```bash
source .venv/bin/activate

# quick smoke test (first 5 tickets, 1 run each)
python tests/eval/run_benchmark.py --limit 5 --repeats 1

# full run (all models, 3× each)
python tests/eval/run_benchmark.py

# a subset of models
python tests/eval/run_benchmark.py --models "Qwen 7B" "GPT-4o-mini"
```

Results are written to `eval/results/<timestamp>__<gitsha>.json` and copied to
`eval/results/latest.json` (which the UI loads by default). Open the **📊 Benchmarks**
tab to see the leaderboard, charts, variance, breakdowns, and worst misses; the tab
also has a **Run quick smoke test** button that shells out to the runner.

Configs skip cleanly (not crash) when a model isn't available: OpenAI configs are
skipped with "no API key" if `OPENAI_API_KEY` is unset, and Ollama configs you haven't
pulled are skipped with an `ollama pull …` hint.

## 3. Reading the metrics

| Column | Meaning |
|--------|---------|
| **Exact %** | Every scored field correct the strict "perfect routing" metric. |
| **Category % / Team %** | The **set** of issue categories / teams matches the expected set (order-independent; single-issue = plain equality). Set-based because a multi-issue ticket has several right answers, not one. |
| **Priority %** | Ticket-level priority matches (null == null for non-tickets). |
| **Review %** | `needs_human_review` matches. |
| **Consistency %** | Of the 3 runs per ticket, the fraction of tickets where **all runs gave the same prediction**. Its own metric because a model can be *accurate on average but unstable* bad for trust. |
| **Valid JSON %** | Model produced schema-valid output (no fallback triggered). |
| **Avg ms** | Mean routing latency per ticket. |

The **consistency-vs-accuracy** view shows Exact % **± the run-to-run stddev**, so
variance is visible rather than hidden behind an average the honest way to compare.

## 4. Why 3× + variance

Local models (and to a lesser extent hosted ones) are **not fully deterministic even at
temperature 0**. A single run can flatter or punish a model by luck. Running 3× and
reporting the spread separates "genuinely better" from "got a lucky draw."

## 5. Caveats

- **Small N** (60 tickets): treat single-digit gaps as noise; look at the stddev.
- **Local variance:** temp-0 still wobbles ±1–2 tickets per run.
- **OpenAI cost/latency:** the GPT configs make real API calls the full 3× run costs
  money and takes longer. Use `--limit` while iterating.
- **Set scoring** rewards getting the right *set* of (category, team) pairs; it does not
  (yet) score per-issue reasoning quality.

## 6. How to add a model

Edit `MODEL_CONFIGS` at the top of `eval/model_configs.py`:

```python
{"name": "My Model", "provider": "ollama", "model": "llama3.1:8b"},   # ollama pull llama3.1:8b
{"name": "GPT-4o",   "provider": "openai", "model": "gpt-4o"},        # needs OPENAI_API_KEY
```

The harness reuses the **same prompt + validation + retry/repair path** as the live app
(`route_ticket_with`), so a new model is judged on exactly the pipeline users get. The
benchmark never writes to the `tickets` database.
