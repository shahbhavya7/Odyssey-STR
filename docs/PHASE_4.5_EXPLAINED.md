# Phase 4.5, Explained (for complete beginners)

## a) What Phase 4.5 does, and why it matters

Phase 4 made the app *work*. Phase 4.5 makes it *look like a real product*. Same
pages, same buttons, same behaviour — we only changed the **skin**: a dark
"liquid-glass" theme with a soft colored glow behind frosted panels, a hand-picked
color identity, and nicer fonts. We also gave the app a name — **Escalio**.

Why bother with looks? The UI is the **demo surface** — it's what people see first. A
clean, distinctive design makes the same functionality feel trustworthy and finished,
and it stops the app looking like a generic template.

Two everyday analogies used throughout:
- **Glassmorphism** = frosted bathroom glass: you can see color and light *through* it,
  but blurred. Our cards are frosted glass laid over a colored glow.
- A **design token** = a paint tin with a label. Instead of writing the color
  `#B65CFF` in fifty places, we fill one labelled tin (`--accent`) and everything dips
  from it — change the tin, the whole app changes.

## b) Every file, explained

| File | What it's for (one line) |
|------|--------------------------|
| `ui/theme.py` (new) | The whole visual system in one place: colors, fonts, the glow background, and the glass look — injected as one stylesheet. |
| `.streamlit/config.toml` | Tells Streamlit to start in dark mode with our colors, so its built-in widgets match. |
| `ui/components.py` (restyled) | The reusable visual pieces — badges, confidence bar, stat cards, the result card — now in glass + the new palette. |
| `ui/app.py` (restyled) | Wires the theme in, renders the hero + sidebar nav, and shows the pages. No logic changed. |
| `docs/PHASE_4.5_EXPLAINED.md` | This file — the plain-English tour of the redesign. |

Nothing in `app/` (the API, routing, database) was touched. This phase is *only* paint.

## c) The design system and components, explained

### The design tokens (in `ui/theme.py`)
All colors and sizes live as **CSS variables** (labelled paint tins) so the look is
consistent and easy to tweak:
- **Base** `--bg-0: #0A0710` — a warm plum-black (not the usual blue-black), so the app
  has its own mood.
- **Accent** `--accent: #B65CFF` (orchid) blending to `--accent-hi: #E85BC6` (magenta) —
  the signature "plasma" gradient on primary buttons and active states, with a gold
  micro-accent `--accent-2: #F5A524`.
- **Text** three shades: `--text-1` (bright, for headings/values), `--text-2` (muted,
  for labels), `--text-3` (faint, for placeholders).
- **Priority colors** `--pri-high` rose, `--pri-med` amber, `--pri-low` mint — the
  traffic-light idea (red = urgent, amber = medium, green = low), tuned for a dark screen.

### The aurora background
Instead of a flat black page, `theme.py` paints three big, heavily-blurred colored
"orbs" (orchid, magenta, gold) fixed behind everything, plus a faint dot texture. This
is what the glass panels blur and refract — **without something colorful behind it,
frosted glass just looks like a grey box.** The orbs drift slowly for a subtle living feel.

### The glass recipe (`_GLASS` in `components.py`)
Every card uses the same recipe: a barely-there white background, a strong **blur of
whatever is behind it** (`backdrop-filter`), a hairline border, a soft drop shadow, and
— crucially — a 1px bright line along the top inside edge. That top highlight is the
trick that makes it read as real glass catching light. This recipe was kept exactly as
it was; only the colors around it changed.

### The pieces (`components.py`)
- **`render_hero(health)`** — the top glass banner with the app name (**Escalio**) and a
  live **status pill**: a green dot + "API connected · provider:model" when the backend
  is up, or a red "API offline" when it isn't.
- **`priority_badge` / `team_badge` / `review_badge`** — small colored "stickers" (pills)
  for fast scanning. Each is a tinted, semi-transparent chip in its own hue.
- **`confidence_bar` / `_confidence_html`** — a thin track with a glowing colored fill
  and a % number; the color follows the same red/amber/green confidence bands.
- **`stat_cards(...)`** — the row of small glass "big number" cards on the Batch page
  (High/Medium/Low counts, % needing review, total time).
- **`result_card(ticket)`** — the hero component: one glass card showing the ticket id,
  category, priority + review badges, the customer message, the assigned team, a
  confidence bar, the routing rationale, and a muted footer (model, prompt version,
  time, timestamp).
- **`offline_panel()`** — an on-theme glass notice (instead of a raw error box) telling
  you how to start the API when it's unreachable.

### The sidebar navigation (`app.py` + `theme.py`)
The left nav is a Streamlit radio control **restyled** into a clean vertical menu: the
round radio dots are hidden and the active item gets an accent left-bar and a soft glow.
The underlying control is unchanged — only its appearance — so page-switching still works
exactly as before.

### What makes the identity *unique* (the point of this phase)
The first draft used the very common indigo-plus-cyan glass look that many AI apps share.
We moved deliberately off it:
- **base:** blue-black → warm plum-ink
- **accent:** indigo/violet → orchid→magenta plasma; **the cyan was dropped** (it was the
  biggest "template" giveaway) in favor of a warm gold in the background glow
- **priority + team colors:** retuned off the default palette
- **display font:** the trendy "Space Grotesk" → **"Bricolage Grotesque"**, with "Inter"
  for body text
Same glass, different soul.

## d) How to run it and what you should see

Two terminals, exactly like Phase 4:
```bash
# Terminal 1 — the API (needs Postgres + Ollama up)
uvicorn app.api:app --reload --port 8000

# Terminal 2 — the UI. Restart it fully after theme changes,
# because .streamlit/config.toml is only read at startup.
streamlit run ui/app.py
```
Then **hard-refresh** the browser (Cmd-Shift-R) — stylesheets get cached, and a stale
one is the #1 reason "my changes don't show."

You should see: a dark app with a soft violet/magenta/gold glow behind frosted glass
panels; the **Escalio** hero with a green "API connected" pill; a glass sidebar whose
active page has an accent bar; and, when you route a ticket, a polished glass result
card. Collapsing the sidebar leaves a small arrow in the top-left to reopen it.

## e) Words you'll hear (mini glossary)

- **Glassmorphism / "liquid glass":** a UI style where panels look like frosted glass —
  translucent and blurring whatever is behind them.
- **`backdrop-filter`:** the CSS feature that does the actual blurring of the background
  behind a glass panel. Needs a modern browser.
- **Aurora / mesh background:** large, soft, blurred color blobs behind everything, so
  the glass has color to refract.
- **CSS variable / design token:** a named, reusable value (like `--accent`) — one place
  to change a color everywhere.
- **Accent color:** the one signature brand color used for emphasis (ours is orchid).
- **Hue:** a specific color (e.g. rose, amber, mint).
- **Badge / pill:** a small rounded colored label for at-a-glance status.
- **Theme (dark/light):** the overall color mode; ours is locked to dark.
- **WCAG AA / contrast:** an accessibility guideline that text must stand out enough from
  its background to stay readable — which is why our bright text sits on dark glass.
- **Hard refresh:** reloading a web page while ignoring the cached files (Cmd-Shift-R),
  so new styles actually load.
