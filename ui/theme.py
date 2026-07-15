"""The visual layer: one injected stylesheet defining the whole design system.

inject_theme() is called once per page render. It sets the design tokens (as CSS
variables), the aurora background + dot texture, a .glass utility, typography, and
overrides for Streamlit's native widgets so everything reads as one system.
"""

import streamlit as st

_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:wght@600;700;800&family=Inter:wght@400;500;600;700&display=swap');

:root {
  --bg-0:#0A0710; --bg-1:#140E1C;
  --accent:#B65CFF; --accent-hi:#E85BC6; --accent-2:#F5A524;
  --text-1:#F5F0FB; --text-2:#B4A9C4; --text-3:#776B85;
  --border:rgba(255,255,255,0.10);
  --glass-bg:rgba(255,255,255,0.045);
  --glass-shadow:0 8px 32px rgba(0,0,0,0.45), inset 0 1px 0 rgba(255,255,255,0.08);
  --pri-high:#FF5C72; --pri-med:#F5A524; --pri-low:#34E0A1;
  --r-card:20px; --r-input:14px; --r-pill:999px;
  --ease:160ms ease;
}

/* ---- Base + fonts ---- */
html, body, [class*="css"], .stApp, [data-testid="stAppViewContainer"] {
  font-family:'Inter', system-ui, sans-serif;
  color:var(--text-1);
}
.stApp { background:var(--bg-0); }

/* Aurora mesh + dot texture, fixed behind all content */
.stApp::before {
  content:""; position:fixed; inset:-10%; z-index:0; pointer-events:none;
  background:
    radial-gradient(46vw 46vw at 14% 8%, rgba(182,92,255,0.22), transparent 60%),
    radial-gradient(42vw 42vw at 86% 18%, rgba(232,91,198,0.16), transparent 60%),
    radial-gradient(50vw 50vw at 62% 96%, rgba(245,165,36,0.10), transparent 62%);
  filter:blur(30px); animation:drift 24s ease-in-out infinite alternate;
}
.stApp::after {
  content:""; position:fixed; inset:0; z-index:0; pointer-events:none; opacity:0.03;
  background-image:radial-gradient(rgba(255,255,255,0.9) 1px, transparent 1px);
  background-size:22px 22px;
}
@keyframes drift { from { transform:translate3d(0,0,0);} to { transform:translate3d(0,-2%,0);} }

/* Content sits above the aurora so glass has something to refract */
[data-testid="stAppViewContainer"] { background:transparent; position:relative; z-index:1; }
[data-testid="stMain"], [data-testid="stHeader"] { background:transparent; }
.block-container { max-width:1100px; padding:2.2rem 2rem 4rem; }

/* Hide only the clutter (Deploy, main menu, footer, decoration) but KEEP the
   header itself so Streamlit's sidebar toggle always stays reachable. */
#MainMenu, [data-testid="stDecoration"],
[data-testid="stStatusWidget"], footer {
  display:none !important;
}
[data-testid="stHeader"], [data-testid="stToolbar"] { background:transparent; }

/* ---- Typography ---- */
h1 { font-family:'Bricolage Grotesque',sans-serif; font-weight:800; letter-spacing:-0.02em; }
h2, h3 { font-family:'Bricolage Grotesque',sans-serif; font-weight:700; letter-spacing:-0.02em; color:var(--text-1); }
.stApp p, .stApp label, .stApp span, .stApp li { color:var(--text-2); }

/* ---- Glass utility ---- */
.glass {
  background:var(--glass-bg);
  backdrop-filter:blur(22px) saturate(150%);
  -webkit-backdrop-filter:blur(22px) saturate(150%);
  border:1px solid var(--border);
  box-shadow:var(--glass-shadow);
  border-radius:var(--r-card);
}

/* ---- Sidebar as glass; radio restyled into a vertical nav ---- */
[data-testid="stSidebar"] {
  background:rgba(14,16,23,0.6);
  backdrop-filter:blur(22px) saturate(150%);
  -webkit-backdrop-filter:blur(22px) saturate(150%);
  border-right:1px solid var(--border);
}
[data-testid="stSidebar"] [role="radiogroup"] { gap:6px; }
[data-testid="stSidebar"] [role="radiogroup"] > label {
  width:100%; padding:10px 12px; border-radius:12px; cursor:pointer;
  border:1px solid transparent; color:var(--text-2); transition:all var(--ease);
  background:transparent;
}
[data-testid="stSidebar"] [role="radiogroup"] > label:hover {
  background:rgba(255,255,255,0.04); color:var(--text-1);
}
/* hide ONLY the circular radio marker (the column that holds the input), keep text */
[data-testid="stSidebar"] [role="radiogroup"] > label > div:first-child:has(input) { display:none; }
[data-testid="stSidebar"] [role="radiogroup"] > label [data-testid="stMarkdownContainer"] { display:block !important; }
[data-testid="stSidebar"] [role="radiogroup"] > label [data-testid="stMarkdownContainer"] p { color:inherit !important; margin:0; }
[data-testid="stSidebar"] [role="radiogroup"] > label:has(input:checked) {
  background:rgba(182,92,255,0.12); color:var(--text-1);
  border-color:rgba(182,92,255,0.35);
  box-shadow:inset 3px 0 0 var(--accent), 0 0 0 3px rgba(182,92,255,0.10);
  font-weight:600;
}
[data-testid="stSidebar"] [role="radiogroup"] > label p { color:inherit !important; font-weight:inherit; }

/* ---- Buttons ---- */
.stButton > button, .stDownloadButton > button {
  border-radius:var(--r-input); border:1px solid var(--border);
  background:var(--glass-bg); color:var(--text-1); font-weight:600;
  padding:0.5rem 1.1rem; transition:all var(--ease);
  backdrop-filter:blur(12px); -webkit-backdrop-filter:blur(12px);
}
.stButton > button:hover, .stDownloadButton > button:hover {
  border-color:var(--accent); color:#fff; transform:translateY(-2px);
  box-shadow:0 8px 22px rgba(182,92,255,0.22);
}
.stButton > button[kind="primary"], [data-testid="stBaseButton-primary"] {
  background:linear-gradient(135deg,var(--accent),var(--accent-hi));
  border:none; color:#fff; box-shadow:0 4px 18px rgba(182,92,255,0.35);
}
.stButton > button[kind="primary"]:hover, [data-testid="stBaseButton-primary"]:hover {
  filter:brightness(1.07); transform:translateY(-2px);
  box-shadow:0 10px 28px rgba(182,92,255,0.5);
}

/* ---- Inputs: dark glass fields with accent focus ---- */
.stTextArea textarea, .stTextInput input, .stNumberInput input {
  background:rgba(255,255,255,0.03) !important; color:var(--text-1) !important;
  border-radius:var(--r-input) !important; border:1px solid var(--border) !important;
}
.stTextArea textarea::placeholder, .stTextInput input::placeholder { color:var(--text-3) !important; }
[data-baseweb="textarea"], [data-baseweb="input"], [data-baseweb="select"] > div {
  background:rgba(255,255,255,0.03) !important; border-radius:var(--r-input) !important;
  border-color:var(--border) !important;
}
.stTextArea textarea:focus, .stTextInput input:focus, .stNumberInput input:focus,
[data-baseweb="select"] > div:focus-within {
  border-color:var(--accent) !important;
  box-shadow:0 0 0 3px rgba(182,92,255,0.25) !important;
}

/* ---- Expander, file uploader, dataframe, progress ---- */
[data-testid="stExpander"] {
  border:1px solid var(--border); border-radius:16px; overflow:hidden;
  background:var(--glass-bg); backdrop-filter:blur(16px);
  -webkit-backdrop-filter:blur(16px);
}
[data-testid="stExpander"] summary:hover { color:var(--text-1); }
[data-testid="stFileUploaderDropzone"] {
  background:rgba(255,255,255,0.03); border:1px dashed var(--border); border-radius:var(--r-input);
}
[data-testid="stDataFrame"] { border:1px solid var(--border); border-radius:16px; overflow:hidden; }
[data-testid="stProgress"] > div > div > div { background:linear-gradient(90deg,var(--accent),var(--accent-2)); }

/* ---- Tame native alerts to the theme ---- */
[data-testid="stAlert"] { border-radius:14px; border:1px solid var(--border); }
</style>
"""


def inject_theme() -> None:
    """Inject the global stylesheet once for the current page render."""
    st.markdown(_CSS, unsafe_allow_html=True)
