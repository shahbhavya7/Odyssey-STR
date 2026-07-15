# Phase 5, Explained (for complete beginners)

## a) What Phase 5 does, and why it matters

Phases 0–4 built a working product. Phase 5 makes it **demoable and provable** the
finishing layer that turns "it works on my machine" into "anyone can run it, and here are
the numbers." Nothing about routing, prompts, or the database changed; this phase is
*additive*.

Five pieces:
1. **A reusable 20-ticket dataset** one file that's both the batch-demo input and (later)
   the eval golden set.
2. **A before/after timing comparison** real, measured proof that the router is faster
   than a human, shown as a "Time Saved" card.
3. **An edge-case hardening pass** proof it *never crashes* on the nasty inputs, written
   down honestly.
4. **A run-cold README** someone who has never seen the project can start it.
5. **A demo script + this explainer** so the mentor demo is smooth and the grading
   questions have prepared answers.

Why it matters for the grade: it directly earns the "problem–solution fit," "handling AI
unreliability," "where does it fail," and "runs from a clean clone" rubric points.

## b) Every new file, explained

| File | What it's for (one line) |
|------|--------------------------|
| `data/sample_tickets.csv` | The 20 varied tickets (id, text) the batch demo input and eval set. |
| `scripts/manual_baseline.py` | A stopwatch: shows you tickets one at a time and times how long *you* take to triage them by hand. |
| `scripts/ai_timing.py` | Routes all 20 tickets and records the router's average time. |
| `tests/test_reliability.py` | Feeds the hardest inputs and asserts a valid result comes back every time. |
| `docs/EDGE_CASES.md` | A table of every tricky input, what happens, and why. |
| `README.md` (rewritten) | Run-from-a-clean-clone instructions, troubleshooting, structure, security. |
| `ARCHITECTURE.md` (new) | The layer-by-layer diagram the README links to. |
| `DEMO_SCRIPT.md` | The step-by-step mentor-demo run sheet + prepared rubric answers. |
| `docs/PHASE_5_EXPLAINED.md` | This file. |

Small additive touches: the Batch page now reads a real CSV's `text` column (so
`sample_tickets.csv` loads cleanly) and shows the **Time Saved** card; `.env.example` was
scrubbed to placeholders and is now committed so a fresh clone gets the template.

## c) The before/after measurement, explained

The claim "AI saves time" is only worth anything if it's **measured**, not guessed. So we
measure both sides honestly:

- **Manual baseline** you run `manual_baseline.py` and actually triage ~10 tickets with a
  stopwatch running. It saves your real average (e.g. ~40 seconds/ticket) to
  `data/manual_baseline.json`. This is *your* number, defensible in the demo.
- **AI timing** `ai_timing.py` routes all 20 tickets and records the router's average
  `processing_ms` to `data/ai_timing.json`.
- **The card** the Batch page reads both files and shows: manual seconds vs AI
  milliseconds, "% faster," and "minutes saved per 100 tickets." If either file is missing,
  it politely tells you to run the scripts instead of crashing. The caption states the
  assumptions (it excludes queueing/hand-off time, so real savings are usually higher) —
  honest math, no inflated claims.

## d) Commands for this phase

```bash
# 1) Measure the human baseline (do ~10 tickets honestly with a stopwatch)
python scripts/manual_baseline.py            # or: --n 20

# 2) With the API running (or offline it falls back), measure the router
python scripts/ai_timing.py

# 3) Prove reliability on the hard inputs
python tests/test_reliability.py

# 4) Reload the Batch Demo page → the Time Saved card is now populated
```

## e) Words you'll hear (mini glossary)

- **Baseline:** the "before" number you compare against here, human triage time.
- **Throughput:** how much work per unit time (tickets/minute). Higher is better.
- **Edge case:** an unusual input that tends to break naive code (empty, huge, foreign
  language, hostile). Handling these *is* the reliability story.
- **Regression:** when a change accidentally breaks something that used to work. Tests
  catch regressions.
- **README:** the front-door document that tells a newcomer how to run the project.
- **Reproducibility:** anyone can follow the steps and get the same working result the
  whole point of the run-cold README.
- **Fallback:** a safe, valid default result returned when something fails, so the service
  never crashes.
- **Prompt injection:** a hostile message that tries to hijack the model's instructions;
  our prompt treats the ticket as data, not commands.
