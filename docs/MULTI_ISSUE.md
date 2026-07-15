# Multi-issue routing, Explained (for complete beginners)

## a) What this change does, and why it matters

Before, Escalio assumed each support message was about **one** thing. But real customers
write things like *"I can't log in **and** I was double-charged."* That's **two** separate
problems for **two** different teams. The old version picked one and mentioned the other
in a sentence the second problem could quietly fall through the cracks.

Now Escalio reads a message, finds **every distinct problem** in it, and tags each one
with its own category, team, and urgency while still giving the whole ticket **one**
urgency level and **one** clearly accountable owner. Nothing gets dropped.

Why it matters: support tickets in the real world are messy and bundled. Routing each
issue to the right team, but keeping one "who's in charge" answer, is what a real triage
system does.

## b) The one big idea, with an analogy

Think of a ticket like a **sticky note with a few to-do items** on it:

- We read the note and write down **each** to-do separately (that's an **issue**: its
  category + team + a one-line reason).
- The whole note gets **one urgency** = the urgency of its **most urgent** item. (A note
  with a "High" item and a "Low" item is a **High** note.)
- The whole note gets **one owner** = the team that owns that most-urgent item the
  **primary team**. That's the "if it slips, who do we ask?" person.
- We still tell **every** team that has something to do (the "routes to" list).

A **single-issue** ticket is just a note with **one** to-do. Same machinery a list that
happens to have one item. There is no separate "single vs multi" code path; that keeps
things simple and bug-free.

Two rules that keep it sensible:
- **Don't over-split.** If someone rants about the same problem three different ways,
  that's still **one** issue, not three. (This is the most common mistake, so the prompt
  is strict about it.)
- **Soft cap of 5.** We pull out up to 5 distinct issues. If a message somehow has more,
  we fold the extras into the closest issue and flag the ticket "needs a human" we never
  silently throw an issue away.

## c) Every file we changed, in plain words

| File | What changed (one line) |
|------|-------------------------|
| `app/schema.py` | The "shape" of a result. Added an `Issue` box, and made a ticket hold a **list** of issues plus the ticket-level urgency, primary team, and a rule-checker that refuses contradictory results. |
| `app/prompts.py` (→ **v1.4**) | The instructions we give the AI: "find each distinct problem, tag each, set the ticket urgency to the highest one, name the primary owner, and don't over-split." Added worked examples. |
| `app/llm_client.py` | Where we talk to the AI. Updated the "you got the format wrong, try again" message to describe the new list shape; the offline stub now returns the new shape too. |
| `app/router_service.py` | The orchestrator. Flattens the AI's answer into a tidy dictionary and adds a safety net: a foreign-language ticket, or a ticket packed with 5 issues, is auto-flagged for a human. |
| `app/models.py` | The database table. Added four columns: the full `issues` list (as JSON), `all_teams` (a comma-joined string, easy to search), `primary_team`, and `primary_issue_index`. |
| `app/repository.py` | Saving + searching. Saves the new columns; the team filter now finds a ticket by **any** team it touches, not just the primary one. |
| `app/api_schemas.py` + `app/api.py` | The web API's input/output shapes. The response now includes the issues list and the teams, for both a freshly-routed ticket and a stored one. |
| `ui/components.py` + `ui/app.py` | The screen. A ticket with several issues now shows a "Routes to: TeamA · TeamB" header, a "primary owner" banner, and a list of all the issues. The batch table gets an "issues" count and a "team load" line. |
| `data/sample_tickets.csv` | Added 3 multi-issue example tickets (ids 21–23) for demos and future scoring. |
| `tests/test_reliability.py` | Rewritten to check the new rules (urgency = the max, primary team matches, at most 5 issues, unknown keys rejected). 12 automated checks. |
| `docs/TEST_CASES.md`, `docs/EDGE_CASES.md` | A copy-paste test matrix, and the edge-case table updated. |

**Important:** the *old* columns (`category`, `priority`, `assigned_team`, `reasoning`)
didn't go away they now hold the **primary** issue's info + the ticket urgency. That's a
deliberate trick so all the existing screens, filters, and queries keep working with no
changes. The new columns simply add the fuller picture beside them.

## d) How the information flows (one trip)

```
You type a message
   → guardrails: empty? redact emails/cards/phones, cap the length
   → the AI reads it and returns: is_ticket + a LIST of issues + ticket urgency + primary owner
   → strict check: unknown key? urgency not the max? contradiction? → try again, then safe fallback
   → safety net: non-English or 5 issues → flag "needs a human"
   → flatten into one tidy dictionary (full list + flat "primary" fields)
   → if it's a real ticket: save ONE row (issues stored as JSON); gibberish is never saved
   → the screen shows one card: one urgency, one owner, all issues, all teams
```

## e) The primary-owner rule (precise version)

> The primary owner is the team of the **most business-critical** issue. If two issues
> tie for the top urgency, pick the more business-critical one **and** flag the ticket for
> human review.

This gives on-call a single "who's accountable" answer while still fanning the work out to
every team that has something to do.

## f) Where it's stored (and the honest trade-off)

We store a **flat primary + a JSON list**:

- The existing flat columns hold the **primary** issue + ticket urgency, so every existing
  query, filter, and screen keeps working with zero changes.
- New columns hold the full picture: `issues` (JSON list), `all_teams` (comma-joined so
  team filtering is a simple `ILIKE`), `primary_team`, `primary_issue_index`.

**What I'd do differently in production:** a normalized `ticket_issues` table (one row per
issue, linked to `tickets`) instead of a JSON blob it makes per-issue reporting and
per-team SLAs a clean `JOIN` rather than digging inside JSON. I kept the JSON approach here
because it's additive, needs no migration framework, and is right-sized for a two-week
project. The production-correct version travels with **Alembic** migrations.

## g) How to run and test it yourself

Automated (no AI needed, instant):
```bash
python tests/test_reliability.py        # expect: All 12 reliability tests passed.
```

Live (API + Ollama up):
```bash
# one problem
python cli.py "I was charged twice, refund please"
# two problems -> two issues, one High priority, primary = Billing
python cli.py "I can't log in AND I was double-charged this month"
# one problem ranted three ways -> exactly ONE issue
python cli.py "Your site is DOWN. It won't load. Nothing works!!!"
```

In the UI: route the two-problem message on **Route a Ticket** → you'll see the
"Routes to: …" header, the primary-owner banner, and both issues listed. Then go to
**Browse & Search** and filter by each of the two teams the same ticket shows up under
both. The full copy-paste test matrix is in [TEST_CASES.md](TEST_CASES.md).

### One-time database step (existing databases only)

`Base.metadata.create_all()` adds the new columns on a **brand-new** database, but it does
**not** alter a table you already have. On an existing dev DB, either drop and recreate the
`tickets` table (loses rows), or add the columns manually (keeps rows):

```sql
ALTER TABLE tickets ADD COLUMN IF NOT EXISTS issues JSON;
ALTER TABLE tickets ADD COLUMN IF NOT EXISTS all_teams VARCHAR;
ALTER TABLE tickets ADD COLUMN IF NOT EXISTS primary_team VARCHAR;
ALTER TABLE tickets ADD COLUMN IF NOT EXISTS primary_issue_index INTEGER;
```

The production-correct answer is a versioned **Alembic** migration.

## h) Words you'll hear (mini glossary)

- **Issue:** one distinct problem inside a ticket has its own category, team, urgency,
  and one-line reason.
- **Ticket-level priority:** the single urgency for the whole ticket = the **highest** of
  its issues' urgencies.
- **Primary team / primary issue:** the owner and the issue that set the ticket's urgency —
  the "who's accountable" answer.
- **all_teams / "routes to":** every team the ticket touches (a 2-team ticket lists both).
- **Over-splitting:** wrongly turning one complaint (said several ways) into several
  issues the mistake we guard against.
- **Soft cap:** the limit of 5 issues; extras are folded in, never dropped, and the ticket
  is flagged for a human.
- **JSON column:** a database column that stores a whole list/object (here, the issues
  list) as text the app can read back as data.
- **Validator:** a rule-checker in the code that rejects a result that contradicts itself
  (e.g. an urgency that isn't the max of the issues), so bad data can't be saved.
- **Strict JSON (`extra="forbid"`):** the result must have *exactly* the expected fields —
  any surprise field is rejected, not silently accepted.
