# Phase 6 (Prompt Lab), Explained (for complete beginners)

## a) What we built in this phase and why

Up to now we *believed* our prompt was good. In this phase we made it **provable**.
We built a small "exam" for the router: a list of support tickets where we already
know the correct answer, plus a script that feeds each one to our system and marks it
right or wrong. That turns a vague claim ("the routing is good") into a real number
("80% correct"). Then we used that number to actually *improve* the prompt twice —
and to add one deterministic safety rule in code. The whole point is honest, measurable
progress instead of guessing.

An everyday analogy: before, we were a student saying "trust me, I studied." Now we sit
a graded mock exam, see exactly which questions we miss, fix those, and re-sit it.

## b) Every file, explained

| File | What it's for (one line) |
|------|--------------------------|
| `eval/golden_set.json` | The **dev exam** 30 tickets with known-correct answers, used to *practise and tune* the prompt. |
| `eval/test_set.json` | The **final exam** 40 fresh tickets the prompt never trained on, used to measure honestly. |
| `eval/golden_set.sample.json` | A 3-ticket mini-exam for a quick sanity check. |
| `eval/run_eval.py` | The **grader** runs every ticket through the router and scores the answers. |
| `eval/README.md` | The lab manual how the exam works and the latest scores. |
| `app/prompts.py` (updated) | The prompt, improved from v1.1 to **v1.2** based on what the exam revealed. |
| `app/router_service.py` (updated) | Added a **non-English safety rule** that always flags foreign-language tickets for a human. |
| `requirements.txt` (updated) | Added `langdetect`, the tool that spots what language a message is in. |

## c) Every change, explained

### The exam data (`eval/golden_set.json`, `eval/test_set.json`)

- **What it is:** A list of tickets, each paired with the *correct* routing (category,
  priority, team, and whether a human should review it). This correct answer is called
  a **label**, and a fully-labeled list is a **golden set** the answer key for our exam.
- **Why two sets:** Once you tweak the prompt to do well on a set of questions, that
  set's score is no longer honest you've *memorised* it. So we keep two: a **dev set**
  to practise on, and a separate **held-out test set** the prompt never sees while
  tuning. If both score about the same, the improvement is real, not memorised. (Ours
  did: ~77% on dev, 80% on the held-out test.)
- **How the labels were made:** A stronger AI (GPT) acted as the **grader/teacher**,
  writing the correct answers by following our exact rulebook. Our smaller local model
  is the **student** being tested.

### The grader (`eval/run_eval.py`)

**`_load(path)`**
- **What it does:** Reads an exam file and, before anything else, checks every "correct
  answer" is a real allowed value (e.g. no made-up team names). If a label is invalid it
  stops loudly, so a typo in the answer key can't silently corrupt the score.
- **Input:** the path to a golden-set file. **Output:** the list of tickets.
- **Why it exists:** A grader with a broken answer key is worse than no grader.

**`main()`**
- **What it does:** For each ticket, it asks the real `route_ticket()` for an answer,
  compares all four fields to the correct answer, and tallies the results. It then prints:
  per-field accuracy (how often each field is right), **exact-match** (all four right at
  once), a breakdown by difficulty (easy/edge/hard), a **review-flag reliability** score
  (did it flag the tickets that needed a human?), and a list of every miss.
- **Input:** optionally a file path (defaults to the dev set). **Output:** a printed
  scorecard.
- **Why it exists:** This single number is how we tell whether a prompt change helped or
  hurt.

### The prompt upgrade: v1.1 → v1.2 (`app/prompts.py`)

The exam exposed three real weaknesses. We fixed each in the prompt:

1. **The "cancel" trap (biggest fix).** For a message like *"add feature X or I'll cancel
   my subscription,"* the model was inventing a payment problem that wasn't there and
   sending it to Billing as urgent. We added a clear rule: a threat to cancel is judged by
   *what the customer actually wants* (usually a **Feature Request**), and you must never
   invent a payment failure. We also added a **worked example** (a **few-shot**, i.e. a
   solved practice question) showing exactly this.
2. **Priority was too twitchy.** The rulebook contradicted itself on "one blocked user,"
   so we made it explicit: **one** user blocked = Medium; things that hit **many** users,
   lose data, or are security/outage/payment problems = High. We also spelled out that
   *lost work counts as data loss* (High), so the model stops under-rating it.
3. **Foreign-language tickets weren't flagged.** The rule to flag non-English messages was
   buried in text, and every worked example was in English, so the model ignored it. We
   made the rule **absolute** ("understanding the message does not cancel the flag") and
   added a **non-English worked example**.

### The safety net in code (`app/router_service.py`)

Even after the prompt fix, a small local model can't be *trusted* to always flag foreign
languages. So we stopped asking nicely and enforced it in code this is our reliability
layer, where "never trust the model blindly" rules live.

**`_is_non_english(text)`**
- **What it does:** Decides whether a message is not in English. It uses `langdetect`
  (a library that guesses a text's language), but guards against its habit of misreading
  short English sentences: if the message clearly contains everyday English words like
  "you," "our," "please," it's treated as English no matter what the detector says.
- **Input:** the message text. **Output:** True/False.
- **Why it exists:** So the safety rule fires on real foreign text but not on ordinary
  English (which would annoy users with needless reviews).

**`_apply_review_guards(ticket, text)`**
- **What it does:** If the message is non-English, it **forces** `needs_human_review` to
  true and lowers the confidence, no matter what the model said.
- **Input:** the model's answer plus the message. **Output:** a corrected answer.
- **Why it exists:** A deterministic guarantee beats hoping the model behaves. This alone
  lifted our "flagged when it should be" score from about 1-in-6 to 5-in-6.

## d) Commands we ran, and what success looks like

| Command | What it does | Successful result |
|---------|--------------|-------------------|
| `pip install -r requirements.txt` | Installs the new `langdetect` tool too. | "Successfully installed…", no errors. |
| `python eval/run_eval.py` | Grades the prompt on the **dev** exam. | A scorecard; exact-match around 77%. |
| `python eval/run_eval.py eval/test_set.json` | Grades on the **held-out** exam. | A scorecard; exact-match around 80%. |
| `python cli.py "No puedo acceder a mi cuenta"` | Routes a Spanish ticket. | `needs_human_review: true` (the guard fired). |
| `python cli.py "the save button does nothing"` | Routes an English ticket. | Routed normally, **not** force-flagged. |

## e) Words you'll hear (mini glossary)

- **Golden set / labeled data:** a list of examples paired with their known-correct
  answers the answer key for the exam.
- **Label:** the correct answer attached to one example.
- **Dev set vs test set:** the practice exam you tune against vs the fresh, held-back exam
  you measure with. Keeping them separate keeps the score honest.
- **Held-out:** data deliberately kept aside and never used for tuning, so it gives an
  unbiased score.
- **Overfitting:** doing well on the exact questions you practised but worse on new ones —
  memorising instead of learning. The test set is how we detect it.
- **Exact-match:** the strictest score all four fields correct on one ticket.
- **Few-shot example:** a solved practice question included in the prompt to teach a tricky
  case by demonstration.
- **langdetect:** a small library that guesses which language a piece of text is written in.
- **Guard / reliability rule:** a check in our own code (not the AI) that enforces safe
  behaviour no matter what the model returns.
- **Deterministic:** always gives the same result for the same input unlike the AI, which
  can wobble slightly between runs.
