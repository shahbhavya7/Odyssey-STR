# Phase 1, Explained 

## a) What Phase 1 does, and why the prompt is the most important part

Phase 0 built the foundation; Phase 1 builds the actual brain. Now a real support
message goes in and structured JSON comes out: which category it is, how urgent, which
team should handle it, a one-line reason, a confidence score, and a "should a human
check this?" flag. The single most important file is `app/prompts.py` — the
**prompt**, which is the set of written instructions we give the AI. The AI is only as
good as its instructions, so most of the care goes there: we spell out every category,
every team, how to send a bug to the *right* engineering team by its symptom, and how
to judge urgency by real business impact instead of by how angry the message sounds.

Just as important: the system **never crashes**. If the AI returns garbage, we retry
with a correction; if it still fails, we hand back a safe "escalate to a human" answer.

## b) Every file, explained

| File | What it's for (one line) |
|------|--------------------------|
| `app/schema.py` (updated) | The contract — now with the real SaaS taxonomy (6 categories, 7 teams incl. engineering). |
| `app/prompts.py` | The graded core: the AI's instruction sheet plus worked examples. |
| `app/llm_client.py` | Talks to the AI (Groq by default, or Ollama / OpenAI), retries on bad output, and has an offline mock. |
| `app/router_service.py` | The one function everything calls: validates, redacts private info, times, never crashes. |
| `cli.py` | A terminal tool to route a ticket by hand and read the JSON result. |
| `docs/PHASE_1_EXPLAINED.md` | This file — the plain-English tour of Phase 1. |

## c) Every function, explained

### In `app/prompts.py`

**`SYSTEM_PROMPT` (a big block of text)**
- **What it is:** The **system prompt** — the standing instructions the AI reads before every ticket, like a job manual handed to a new triage clerk. It defines the 6 categories, the 7 teams, the symptom rules for bugs, the priority rubric, and the exact JSON to return.
- **Why it exists:** This is where the routing *rules* live. Change behaviour here, not in code.

**`FEW_SHOT_EXAMPLES` (a list of example messages)**
- **What it is:** A handful of solved examples — a customer message paired with the perfect JSON answer. Showing worked examples is called **few-shot** prompting (as opposed to **zero-shot**, giving no examples). It's like handing someone worked problems before a test.
- **Why it exists:** Examples teach the tricky calls far better than rules alone — especially "angry typo = Low priority" and how to tell a Frontend bug from a Backend or DevOps one.

**`build_messages(ticket_text)`**
- **What it does:** Stacks the instruction sheet, then the worked examples, then the new ticket, into the list the AI expects.
- **Inputs:** the ticket text (already cleaned of private info).
- **Output:** a list of message dicts.
- **Why it exists:** So every request is assembled the same way, in one place.

### In `app/llm_client.py`

**`LLMError` (a custom exception)**
- **What it is:** Our own error type, raised only when the AI fails every attempt. A named error lets the service above catch *exactly* this case and fall back cleanly.

**`_make_client()`**
- **What it does:** Builds the connection object pointed at whichever provider is switched on — hosted Groq (the default), local Ollama, or OpenAI. All three speak the same "language," so one code path serves them all.
- **Output:** a ready-to-use client.
- **Why it exists:** So switching providers is one setting, not a rewrite.

**`route_with_llm(ticket_text)` — the retry + repair loop (the heart of reliability)**
- **What it does:** Sends the ticket to the AI and gets a routing back. If the reply is empty, isn't valid JSON, or doesn't fit our contract, it **retries** — and on a retry it appends a blunt correction ("return ONLY a JSON object with exactly these keys"). It waits a bit longer between tries (a "backoff"). If every attempt fails, it raises `LLMError`.
  - **Parsing** = turning the AI's text reply into real data. **Validation** = checking that data has the right fields and types (Pydantic does this). **JSON mode** = asking the AI to reply as a strict JSON object, not chatty prose.
- **Inputs:** the ticket text.
- **Output:** a `(RoutedTicket, engine_name)` pair, where `engine_name` is like `ollama:qwen2.5:7b`.
- **Why it exists:** AIs are occasionally sloppy. This loop turns "sometimes wrong shape" into "always the right shape, or a clean, named failure."

**`_repair_message()`**
- **What it does:** Writes the corrective note appended after a bad reply, listing the exact required keys.
- **Why it exists:** A second try with a pointed correction usually fixes a one-off formatting slip.

**`_mock_route(ticket_text)`**
- **What it does:** A tiny keyword matcher (no AI) that returns a valid result — e.g. "refund" → Billing. It's a stand-in used only when `use_mock` is on.
- **Why it exists:** So the whole app runs offline with no model at all, and demos never hard-depend on a running AI.

### In `app/router_service.py`

**`_redact_pii(text)`**
- **What it does:** **PII redaction** — scrubbing Personally Identifiable Information. It replaces email addresses with `[EMAIL]`, card-like 13–16-digit numbers with `[CARD]`, and phone-like numbers with `[PHONE]` *before* any text is sent to the AI.
- **Inputs/Output:** text in, cleaned text out.
- **Why it exists:** Private data should never leave the building unnecessarily — basic privacy hygiene.

**`_to_dict(...)`**
- **What it does:** Flattens the validated ticket plus metadata (engine, prompt version, how many milliseconds it took, any error) into one plain dictionary ready to print or store.
- **Why it exists:** Every caller — CLI now, API and UI later — gets the same predictable shape.

**`route_ticket(raw_text)` — the one entry point**
- **What it does:** The front door. It (1) starts a timer; (2) if the input is empty, returns a safe fallback immediately **without calling the AI**; (3) truncates very long input and redacts private info; (4) calls `route_with_llm`; (5) if that raises `LLMError`, returns a safe "escalate to a human" result labelled `engine="fallback"`. It **never** throws an error back to whoever called it.
- **Inputs:** the raw customer message.
- **Output:** the result dictionary.
- **Why it exists:** All the "be safe, be reliable" logic that isn't the AI itself lives here, in one reusable place.

### In `cli.py`

**`_print_result(text)`**
- **What it does:** Routes one ticket and prints the result as nicely indented JSON.

**`main()`**
- **What it does:** If you passed text on the command line, it routes that once; otherwise it starts an interactive loop asking for tickets until you press Ctrl+C.
- **Why it exists:** A fast way to test routing by hand before any web UI exists.

### How bug sub-routing works (the triage-nurse idea)

A "Bug & Outage" ticket doesn't go to one generic engineering team — it's sent to a
**specialist by symptom**, exactly like a triage nurse sending you to the right doctor:
- You can **see** it (button dead, layout broken, typo) → **Frontend / UI-UX**.
- The **data or logic** is wrong (500 error, wrong totals, save fails) → **Backend / API**.
- The whole thing is **unreachable** (site down, everything timing out) → **DevOps / Infrastructure**.
- If it's genuinely unclear which, we still pick the closest one but flag it for a human.

## d) Commands we ran, and what success looks like

| Command | What it does | Successful result |
|---------|--------------|-------------------|
| `python cli.py "I was charged twice, refund please"` | Routes a billing ticket. | Billing & Payments / Billing Team / High. |
| `python cli.py "the Save button does nothing when I click it"` | A visible UI bug. | Bug & Outage / Frontend / UI-UX. |
| `python cli.py "API returns 500 and my data is wrong"` | A data/logic bug. | Bug & Outage / Backend / API. |
| `python cli.py "your site has been down for an hour"` | An availability bug. | Bug & Outage / DevOps / Infrastructure / High. |
| `python cli.py "help"` | Too vague to classify. | needs_human_review true, low confidence. |
| `python cli.py ""` | Empty input. | `error: empty_input`, no AI call. |
| `python cli.py "RIDICULOUS!!! typo on your page"` | Angry but trivial. | priority Low (tone ≠ priority). |
| Same input twice | Determinism check. | Identical result (temperature 0). |
| Stop Ollama, run any ticket | Failure check. | Clean `engine: fallback`, no crash. |

## e) Words you'll hear (mini glossary)

- **Prompt:** the written instructions we give the AI. The better the prompt, the better the answers.
- **System prompt:** the standing instructions the AI reads before every ticket — its job manual.
- **Few-shot vs zero-shot:** few-shot = we show worked examples first (like practice problems before a test); zero-shot = we show none.
- **Temperature:** a "creativity dial" from 0 upward. We use **0** = always give the single safest, most consistent answer, so the same ticket routes the same way every time.
- **JSON mode:** asking the AI to reply as a strict JSON object (structured data), not chatty text.
- **Parsing:** turning the AI's text reply into real, usable data.
- **Validation:** checking that data has the required fields, types, and limits (Pydantic does this for us).
- **Retry:** trying again after a failure — here, with a correction attached.
- **Fallback:** a guaranteed safe answer when everything else fails — the spare tire that gets you home.
- **PII redaction:** scrubbing Personally Identifiable Information (emails, card and phone numbers) out of text before sending it anywhere.
