# `schema.py` — the shape of a valid answer

**In plain words:** this file defines *exactly* what a routed ticket must look like, using
Pydantic (a library that checks data shapes). The star trick here is **enums**: the
category, priority, and team can only ever be one of a fixed list of allowed values. If the
model tries to return `"Priority": "Urgent"` (not on the list), validation *rejects* it —
so an invalid value can't sneak into our database.

**Beginner terms:**
- **Enum** = a fixed menu of allowed choices. Nothing outside the menu is accepted.
- **Pydantic model** = a Python class that automatically validates its data on creation.

---

## `class Category(str, Enum)`

- **What it is:** the fixed list of ticket types: Billing & Payments, Account & Access,
  How-To / Usage, Bug & Outage, Feature Request, General / Other.
- **`str, Enum`:** it's an enum *and* behaves like a string, so it drops straight into JSON.

## `class Priority(str, Enum)`

- **What it is:** the only three urgency levels: `High`, `Medium`, `Low`. Nothing else exists.

## `class Team(str, Enum)`

- **What it is:** the seven teams a ticket can go to (Billing Team, Account Management,
  Customer Support, Product, Frontend / UI-UX, Backend / API, DevOps / Infrastructure).

## `class RoutedTicket(BaseModel)` — *the contract*

- **What it is:** the full validated result of routing one ticket. Every field is checked:
  - `category`, `priority`, `assigned_team` — must be from the enums above.
  - `reasoning` — a short string, **max 200 characters** (a one-liner, enforced).
  - `confidence` — a number that **must be between 0.0 and 1.0** (Pydantic rejects `1.5`).
  - `needs_human_review` — `True`/`False` flag for "a person should double-check this".
- **Why it matters:** if the model's JSON doesn't fit *all* these rules, creating a
  `RoutedTicket(**data)` throws an error — which is exactly how `llm_client` knows to
  retry or repair. The shape is the safety gate.

## `safe_fallback(reason: str) -> RoutedTicket`

- **What it does:** builds a guaranteed-valid "we couldn't route this, send it to a human"
  result.
- **Inputs:** `reason` — a short explanation (trimmed to 200 chars) of what went wrong.
- **Returns:** a `RoutedTicket` set to General / Medium / Customer Support, `confidence=0.0`,
  and `needs_human_review=True`.
- **Why it matters:** this is the promise that the service **never crashes**. On empty input,
  a dead model, or garbage JSON, we still hand back a usable, valid result — just flagged for
  a human instead of pretending we're sure.
