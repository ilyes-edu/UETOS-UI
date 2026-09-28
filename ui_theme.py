"""UETOS - interface theme for the Streamlit pages (CSS only).

Wired into app.py with two lines (already present in the kit's app.py):

    from ui_theme import apply_ui_theme      # next to the other imports
    apply_ui_theme(st)                        # just before the .app-hero banner

apply_ui_theme() only injects a <style> block. It reads no data, changes no session state and does
not touch the scheduling / editing logic. Colours match .streamlit/config.toml and the dnd_* components.
"""

_CSS = """
<style>
@import url("https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+Arabic:wght@400;500;600;700&display=swap");

:root {
  --u-accent: #1f6fa8;
  --u-accent-2: #2a86bf;
  --u-line: #d9e3ee;
  --u-shadow: 0 1px 2px rgba(15, 35, 60, .05), 0 6px 20px rgba(15, 35, 60, .06);
}

/* style-only st.markdown blocks (like this one) must not leave empty gaps on the page */
div[data-testid="stElementContainer"]:has(div[data-testid="stMarkdownContainer"] > style):not(:has(div[data-testid="stMarkdownContainer"] > :not(style))) {
  display: none;
}

/* typography - fallback when .streamlit/config.toml is not used */
.stApp, .stApp [data-testid="stMarkdownContainer"], .stApp [data-testid="stWidgetLabel"], .stApp input, .stApp textarea {
  font-family: "IBM Plex Sans Arabic", "Source Sans Pro", "Segoe UI", Tahoma, sans-serif;
}

/* page */
.stApp {
  background-image:
    radial-gradient(1100px 420px at 100% -8%, rgba(42, 134, 191, .09), transparent 60%),
    radial-gradient(900px 360px at -10% 0%, rgba(31, 111, 168, .05), transparent 55%);
  background-attachment: fixed;
}
.block-container, [data-testid="stMainBlockContainer"] { max-width: 1560px; padding-top: 1.2rem; padding-bottom: 3rem; }
header[data-testid="stHeader"] { background: rgba(245, 248, 252, .78); backdrop-filter: blur(10px); -webkit-backdrop-filter: blur(10px); }
div[data-testid="stDecoration"] { display: none; }
.stApp h1, .stApp h2, .stApp h3 { letter-spacing: -.01em; }

/* banner */
.app-hero {
  position: relative; overflow: hidden; isolation: isolate;
  background: linear-gradient(115deg, #13304e 0%, #1d5a88 52%, #2a86bf 100%);
  border: 1px solid rgba(255, 255, 255, .08); border-radius: 18px;
  padding: 20px 26px 18px; margin-bottom: 18px; box-shadow: 0 12px 32px rgba(19, 48, 78, .22);
}
.app-hero::before {
  content: ""; position: absolute; inset: 0; z-index: -1; pointer-events: none;
  background:
    radial-gradient(520px 220px at 88% -40%, rgba(255, 255, 255, .20), transparent 62%),
    repeating-linear-gradient(90deg, rgba(255, 255, 255, .045) 0 1px, transparent 1px 46px),
    repeating-linear-gradient(0deg, rgba(255, 255, 255, .035) 0 1px, transparent 1px 46px);
}
.app-hero-title { font-size: 1.7rem; font-weight: 700; letter-spacing: -.01em; }
.beta-badge { background: #ffcf5c; color: #3a2900; box-shadow: 0 2px 10px rgba(0, 0, 0, .18); }
.app-hero-sub { opacity: .9; margin-top: 6px; }

/* sidebar + page menu (the navigation radio has key="page") */
section[data-testid="stSidebar"] [data-testid="stSidebarContent"] {
  background-image: linear-gradient(180deg, rgba(255, 255, 255, .55), rgba(255, 255, 255, 0) 260px);
}
.st-key-page [role="radiogroup"] { gap: .3rem; }
.st-key-page label[data-baseweb="radio"] {
  width: 100%; margin: 0; padding: .5rem .7rem; border-radius: 12px; border: 1px solid transparent;
  transition: background .15s ease, border-color .15s ease, box-shadow .15s ease;
}
.st-key-page label[data-baseweb="radio"]:hover { background: rgba(31, 111, 168, .07); }
.st-key-page label[data-baseweb="radio"]:has(input:checked) {
  background: rgba(255, 255, 255, .92); border-color: var(--u-line); box-shadow: var(--u-shadow);
}
.st-key-page label[data-baseweb="radio"]:has(input:checked) p { color: var(--u-accent); font-weight: 600; }

/* buttons */
.stButton > button, .stDownloadButton > button, .stFormSubmitButton > button {
  font-weight: 600; transition: transform .12s ease, box-shadow .12s ease;
}
.stButton > button:not(:disabled):hover, .stDownloadButton > button:not(:disabled):hover, .stFormSubmitButton > button:not(:disabled):hover {
  transform: translateY(-1px); box-shadow: 0 6px 16px rgba(15, 35, 60, .12);
}
.stButton > button[kind="primary"]:not(:disabled), .stDownloadButton > button[kind="primary"]:not(:disabled),
.stFormSubmitButton > button[kind="primary"]:not(:disabled) {
  background-image: linear-gradient(135deg, var(--u-accent), var(--u-accent-2));
  border-color: transparent; box-shadow: 0 4px 14px rgba(31, 111, 168, .28);
}

/* cards, panels, inputs */
div[data-testid="stMetric"] { border-radius: 14px; padding: 12px 16px; box-shadow: var(--u-shadow); }
div[data-testid="stMetricValue"] { font-weight: 700; letter-spacing: -.01em; }
div[data-testid="stExpander"] details { border-radius: 14px; box-shadow: 0 1px 2px rgba(15, 35, 60, .04); }
div[data-testid="stExpander"] summary { font-weight: 600; }
div[data-testid="stExpander"] summary:hover { color: var(--u-accent); }
div[data-testid="stAlertContainer"] { border-radius: 12px; }
div[data-testid="stFileUploaderDropzone"] { border-radius: 14px; border-width: 1.5px; border-style: dashed; transition: border-color .15s ease; }
div[data-testid="stFileUploaderDropzone"]:hover { border-color: var(--u-accent); }
div[data-testid="stDataFrame"] { border-radius: 12px; }
div[role="dialog"] { border-radius: 18px; }
.small-screen { border-radius: 12px !important; }

/* scrollbars */
.stApp ::-webkit-scrollbar { width: 10px; height: 10px; }
.stApp ::-webkit-scrollbar-thumb { background: rgba(98, 117, 138, .35); border-radius: 10px; border: 2px solid transparent; background-clip: content-box; }

@media print {
  header[data-testid="stHeader"], section[data-testid="stSidebar"] { display: none; }
}
@media (prefers-reduced-motion: reduce) {
  .stButton > button, .stDownloadButton > button, .st-key-page label[data-baseweb="radio"] { transition: none; }
}
</style>
"""


def apply_ui_theme(st):
    """Inject the UETOS look and feel. Safe to call on every rerun; changes nothing but CSS."""
    st.markdown(_CSS, unsafe_allow_html=True)
