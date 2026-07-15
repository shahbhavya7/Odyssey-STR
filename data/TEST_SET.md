# Escalio Sample Test Set & Answer Key

The 20 tickets below are the demo set. They live in machine-readable form in
[`sample_tickets.csv`](sample_tickets.csv) the Streamlit **batch mode** routes all 20 in one click.

- **Table 1 Answer key:** each ticket with its *intended* classification (expected output),
  derived from the v1.2 prompt rubric in [`app/prompts.py`](../app/prompts.py). Use this to eyeball
  whether the model got it right.
- **Table 2 Queries only:** copy-paste one at a time into the single-ticket form.

Enums: **Category** = Billing & Payments · Account & Access · How-To / Usage · Bug & Outage ·
Feature Request · General / Other. **Priority** = High / Medium / Low. **Teams** = Billing Team ·
Account Management · Customer Support · Product · Frontend / UI-UX · Backend / API · DevOps / Infrastructure.

Priority is by **business impact, not tone**: High = many users / data loss / security / outage /
payment blocked; Medium = one user fully blocked; Low = cosmetic / questions / feature ideas.

---

## Table 1 Answer key (ticket → intended classification)

| # | Ticket | Category | Priority | Assigned team | Review? | Why / edge case |
|---|--------|----------|----------|---------------|:------:|-----------------|
| 1 | I was charged twice for my Pro subscription this month please refund the duplicate charge. | Billing & Payments | High | Billing Team | No | Duplicate charge = payment failure affecting money. |
| 2 | I can't log in. My password reset email never arrives, even after three tries. | Account & Access | Medium | Account Management | No | One user blocked → Medium, not High. |
| 3 | How do I export my project data to a CSV file? | How-To / Usage | Low | Customer Support | No | "How do I…" on an existing feature. |
| 4 | The Save button on the settings page does nothing when I click it. | Bug & Outage | Medium | Frontend / UI-UX | No | Unresponsive visible button = UI symptom. |
| 5 | Your API returns a 500 error on POST /orders and my order totals are coming back wrong. | Bug & Outage | High | Backend / API | No | 500 + wrong data = backend logic failure. |
| 6 | Your entire website has been down for the last 40 minutes and nobody on my team can work. | Bug & Outage | High | DevOps / Infrastructure | No | Total outage = availability, affects everyone. |
| 7 | It would be great if you added a dark mode to the dashboard. | Feature Request | Low | Product | No | New capability that doesn't exist yet. |
| 8 | Hi, I just wanted to reach out because I have a question about your service. | General / Other | Low | Customer Support | **Yes** | No actual question stated → too vague, flag. |
| 9 | This is absolutely ridiculous!!! There is a typo on your pricing page. Fix it. | Bug & Outage | Low | Frontend / UI-UX | No | Cosmetic typo; angry tone does NOT raise priority. |
| 10 | help | General / Other | Low | Customer Support | **Yes** | One vague word → flag for review. |
| 11 | It's not working. | General / Other | Low | Customer Support | **Yes** | No detail; ambiguous which product/area → flag. |
| 12 | I was double charged AND now I can't log in to update my payment details please help with both. | Billing & Payments | High | Billing Team | No | Multi-issue: route by biggest impact (billing High > login Medium); name login as secondary. |
| 13 | If this isn't resolved today I am cancelling my subscription and moving to a competitor. | General / Other | Low | Customer Support | **Yes** | Churn threat with NO stated issue; do not invent a billing problem → flag. |
| 14 | No puedo iniciar sesión en mi cuenta y necesito acceder a mis facturas. | Account & Access | Medium | Account Management | **Yes** | Non-English → route by meaning (login/access) but flag is ABSOLUTE, confidence ≤ 0.4. |
| 15 | All of my saved documents vanished from my account overnight this is critical work I need back. | Bug & Outage | High | Backend / API | No | Data loss = High even for one user; lost data = backend. |
| 16 | Where can I find a copy of last month's invoice for my records? | Billing & Payments | Low | Billing Team | No | Informational billing request, no blocked work. |
| 17 | I lost my phone and can't get past two-factor authentication to sign in. | Account & Access | Medium | Account Management | No | One user blocked from access → Medium. |
| 18 | How can I connect your app to our Slack workspace? | How-To / Usage | Low | Customer Support | No | "How do I…" usage question. |
| 19 | Please consider adding a Zapier integration so we can automate exporting our tickets. | Feature Request | Low | Product | No | Requests a new integration that doesn't exist. |
| 20 | The reports page takes over 30 seconds to load and sometimes times out completely. | Bug & Outage | Medium | Backend / API | Borderline | Slow endpoint = perf/backend; sub-team Backend-vs-DevOps is arguable, low confidence acceptable. |

**Edge cases covered:** angry-but-minor (#9), very short / near-empty (#8, #10, #11), ambiguous (#11, #13),
multi-issue (#12), non-English (#14), data loss (#15), churn threat (#13), sub-team ambiguity (#20).

---

## Table 2 Queries only (copy-paste for one-by-one testing)

| # | Query |
|---|-------|
| 1 | I was charged twice for my Pro subscription this month please refund the duplicate charge. |
| 2 | I can't log in. My password reset email never arrives, even after three tries. |
| 3 | How do I export my project data to a CSV file? |
| 4 | The Save button on the settings page does nothing when I click it no error, it just doesn't respond. |
| 5 | Your API returns a 500 error on POST /orders and my order totals are coming back wrong. |
| 6 | Your entire website has been down for the last 40 minutes and nobody on my team can work. |
| 7 | It would be great if you added a dark mode to the dashboard. |
| 8 | Hi, I just wanted to reach out because I have a question about your service. |
| 9 | This is absolutely ridiculous!!! There is a typo on your pricing page it says 'montly' instead of 'monthly'. Fix it. |
| 10 | help |
| 11 | It's not working. |
| 12 | I was double charged AND now I can't log in to update my payment details please help with both. |
| 13 | If this isn't resolved today I am cancelling my subscription and moving to a competitor. |
| 14 | No puedo iniciar sesión en mi cuenta y necesito acceder a mis facturas. |
| 15 | All of my saved documents vanished from my account overnight this is critical work I need back. |
| 16 | Where can I find a copy of last month's invoice for my records? |
| 17 | I lost my phone and can't get past two-factor authentication to sign in. |
| 18 | How can I connect your app to our Slack workspace? |
| 19 | Please consider adding a Zapier integration so we can automate exporting our tickets. |
| 20 | The reports page takes over 30 seconds to load and sometimes times out completely. |

> **Batch demo:** open Streamlit → Batch mode → upload [`sample_tickets.csv`](sample_tickets.csv)
> (or paste the queries above) → routes all 20 at once and shows the results table.
