"""
Bluesky Growth — Terminal Style Dashboard
Streamlit app for managing Bluesky follow/like/unfollow bots.
"""

import streamlit as st
import streamlit.components.v1 as components
import time
import subprocess
import threading
from datetime import datetime


def get_version():
    """Get version from git commit hash."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            cwd="/Users/samuel/projects/bluesky-engine"
        )
        if result.returncode == 0:
            return f"v{result.stdout.strip()}"
    except:
        pass
    return "v1.0"

from atproto.exceptions import AtProtocolError
from utils.auth import login
from utils.stats import get_stats
from utils.tracker import load_history, save_snapshot, get_chart_data
from bots.like_bot import like_bot_run
from bots.follow_bot import follow_bot_run
from bots.unfollow_bot import unfollow_bot_run, get_unfollow_preview


# =============================================================
# CACHED BLUESKY CLIENT
# =============================================================

@st.cache_resource
def get_bluesky_client(handle: str, password: str):
    """Returns a cached authenticated client. Reused across reruns."""
    return login(handle, password)


# =============================================================
# THREAD-SAFE BOT RUNNER
# =============================================================

class BotRunner:
    """Manages bot execution in a background thread with thread-safe state."""

    def __init__(self):
        self._lock = threading.Lock()
        self._thread = None
        self._running = False
        self._stop_requested = False
        self._log_lines = []
        self._results = None
        self._error = None

    @property
    def running(self):
        with self._lock:
            return self._running

    @property
    def stop_requested(self):
        with self._lock:
            return self._stop_requested

    def start(self, bot_func, *args, **kwargs):
        """Start bot in background thread."""
        with self._lock:
            if self._running:
                return False
            self._running = True
            self._stop_requested = False
            self._log_lines = []
            self._results = None
            self._error = None

        def run():
            try:
                # Add stop_check to kwargs
                kwargs['stop_check'] = lambda: self.stop_requested
                # Create thread-safe log callback
                def log_callback(line):
                    with self._lock:
                        self._log_lines.append(line)
                kwargs['log_callback'] = log_callback
                # Run the bot
                results = bot_func(*args, **kwargs)
                with self._lock:
                    self._results = results
            except Exception as e:
                with self._lock:
                    self._error = str(e)
            finally:
                with self._lock:
                    self._running = False

        self._thread = threading.Thread(target=run, daemon=True)
        self._thread.start()
        return True

    def stop(self):
        """Request bot to stop."""
        with self._lock:
            self._stop_requested = True

    def get_logs(self):
        """Get current log lines (thread-safe)."""
        with self._lock:
            return self._log_lines.copy()

    def get_results(self):
        """Get bot results (thread-safe)."""
        with self._lock:
            return self._results

    def get_error(self):
        """Get error message (thread-safe)."""
        with self._lock:
            return self._error

    def clear(self):
        """Clear all state."""
        with self._lock:
            self._running = False
            self._stop_requested = False
            self._log_lines = []
            self._results = None
            self._error = None


# Global bot runners (persists across Streamlit reruns)
if 'like_runner' not in st.session_state:
    st.session_state.like_runner = BotRunner()

if 'follow_runner' not in st.session_state:
    st.session_state.follow_runner = BotRunner()

if 'unfollow_runner' not in st.session_state:
    st.session_state.unfollow_runner = BotRunner()


def any_bot_running():
    """Check if any bot is currently running."""
    return (st.session_state.like_runner.running or
            st.session_state.follow_runner.running or
            st.session_state.unfollow_runner.running)


def get_running_bot_name():
    """Get the name of the currently running bot."""
    if st.session_state.like_runner.running:
        return "LIKE"
    elif st.session_state.follow_runner.running:
        return "FOLLOW"
    elif st.session_state.unfollow_runner.running:
        return "UNFOLLOW"
    return None


@st.fragment(run_every=2)
def live_log_panel(runner: BotRunner):
    """Self-refreshing log panel that doesn't freeze the UI."""
    logs = runner.get_logs()
    if logs:
        # Show newest first (descending order)
        log_text = "\n".join(reversed(logs[-50:]))
        st.code(log_text, language="bash")
    else:
        st.code("Starting bot...", language="bash")
    if not runner.running:
        st.rerun()


def send_notification(title: str, body: str):
    """Send a browser notification if permission is granted."""
    components.html(f"""
    <script>
    if ("Notification" in window && Notification.permission === "granted") {{
        new Notification("{title}", {{body: "{body}"}});
    }}
    </script>
    """, height=0)


# =============================================================
# PAGE CONFIG
# =============================================================

st.set_page_config(
    page_title="bluesky-engine",
    page_icon="🦋",
    layout="wide",
    initial_sidebar_state="expanded",
)

# =============================================================
# CUSTOM CSS — Terminal Style
# =============================================================

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&display=swap');

/* Override Streamlit defaults */
.stApp {
    background: #0a0a0a;
    color: #c8c8c8;
}

/* Hide Streamlit running indicator (top right spinner) */
.stStatusWidget,
header[data-testid="stHeader"] .stSpinner,
.stSpinner {
    display: none !important;
}

/* Override Streamlit alert widgets to match dark theme */
div[data-testid="stAlert"],
div.stAlert,
.element-container div[data-baseweb="notification"] {
    background: #111 !important;
    border: 1px solid #333 !important;
    border-radius: 4px !important;
    color: #c8c8c8 !important;
}
div[data-testid="stAlert"] > div,
div.stAlert > div,
.element-container div[data-baseweb="notification"] > div {
    color: #c8c8c8 !important;
    background: transparent !important;
}
/* Warning — subtle orange border */
div[data-testid="stWarning"],
div[data-baseweb="notification"][kind="warning"] {
    border-left: 3px solid #ff8800 !important;
    background: #1a1500 !important;
}
/* Info — subtle blue border */
div[data-testid="stInfo"],
div[data-baseweb="notification"][kind="info"] {
    border-left: 3px solid #00d4ff !important;
    background: #001a22 !important;
}
/* Error — subtle red border */
div[data-testid="stError"],
div[data-baseweb="notification"][kind="error"] {
    border-left: 3px solid #ff4444 !important;
    background: #1a0000 !important;
}
/* Success — subtle green border */
div[data-testid="stSuccess"],
div[data-baseweb="notification"][kind="success"] {
    border-left: 3px solid #00ff88 !important;
    background: #001a0d !important;
}

/* Main content area */
.main .block-container {
    padding-top: 2rem;
    padding-bottom: 2rem;
    max-width: 1400px;
}

/* Typography */
h1, h2, h3, h4, h5, h6, p, span, div, label {
    font-family: 'JetBrains Mono', monospace !important;
    color: #c8c8c8;
}

/* Form spacing — consistent 12px between elements */
.stForm > div > div > div {
    margin-bottom: 12px !important;
}
.stForm > div > div > div:last-child {
    margin-bottom: 0 !important;
}

/* Metric tooltip */
[data-tooltip] {
    position: relative;
    cursor: help;
}
[data-tooltip]:hover::after {
    content: attr(data-tooltip);
    position: absolute;
    bottom: 100%;
    left: 50%;
    transform: translateX(-50%);
    background: #222;
    color: #c8c8c8;
    padding: 8px 12px;
    border-radius: 4px;
    font-size: 11px;
    font-family: 'JetBrains Mono', monospace;
    white-space: normal;
    word-wrap: break-word;
    max-width: 220px;
    width: max-content;
    z-index: 1000;
    border: 1px solid #444;
    box-shadow: 0 4px 12px rgba(0,0,0,0.5);
    text-transform: none;
    letter-spacing: 0;
}
[data-tooltip]:hover::before {
    content: '';
    position: absolute;
    bottom: 100%;
    left: 50%;
    transform: translateX(-50%);
    border: 5px solid transparent;
    border-top-color: #444;
    margin-bottom: -5px;
    z-index: 1000;
}

/* Topbar */
/* Sidebar - always visible */
[data-testid="stSidebar"] {
    background: #111;
    border-right: 1px solid #222;
    padding: 20px 16px;
    min-width: 200px !important;
    max-width: 200px !important;
}
/* Hide collapse/expand buttons - sidebar always shown */
[data-testid="stSidebarCollapseButton"],
[data-testid="stSidebarCollapsedControl"],
button[kind="header"] {
    display: none !important;
}
/* Force sidebar always visible */
section[data-testid="stSidebar"] {
    transform: translateX(0) !important;
    visibility: visible !important;
    position: relative !important;
}
/* Sidebar nav buttons — base reset for all button types */
section[data-testid="stSidebar"] button[kind="secondary"],
section[data-testid="stSidebar"] button[kind="primary"],
section[data-testid="stSidebar"] button[kind="tertiary"] {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    color: #999 !important;
    -webkit-text-fill-color: #999 !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 12px !important;
    -webkit-text-size-adjust: 100% !important;
    text-transform: uppercase !important;
    letter-spacing: 1px !important;
    padding: 6px 8px !important;
    margin: 0 !important;
    text-align: left !important;
    justify-content: flex-start !important;
}
/* Remove gap between sidebar button containers */
section[data-testid="stSidebar"] .stButton {
    margin-bottom: 0 !important;
    padding-bottom: 0 !important;
}
section[data-testid="stSidebar"] .stButton > div {
    margin-bottom: 0 !important;
    padding-bottom: 0 !important;
}
section[data-testid="stSidebar"] .element-container {
    margin-bottom: 0 !important;
    padding-bottom: 0 !important;
}
section[data-testid="stSidebar"] button[kind="secondary"] p,
section[data-testid="stSidebar"] button[kind="primary"] p,
section[data-testid="stSidebar"] button[kind="tertiary"] p,
section[data-testid="stSidebar"] button[kind="secondary"] span,
section[data-testid="stSidebar"] button[kind="primary"] span,
section[data-testid="stSidebar"] button[kind="tertiary"] span {
    font-size: 12px !important;
    text-align: left !important;
    justify-content: flex-start !important;
    border-radius: 2px !important;
    transition: all 0.15s ease !important;
    width: 100% !important;
    margin-bottom: 0 !important;
}
section[data-testid="stSidebar"] button[kind="secondary"]:hover,
section[data-testid="stSidebar"] button[kind="primary"]:hover,
section[data-testid="stSidebar"] button[kind="tertiary"]:hover {
    color: #c8c8c8 !important;
    -webkit-text-fill-color: #c8c8c8 !important;
    background: #1a1a1a !important;
}
/* Inactive nav button — explicit secondary override */
section[data-testid="stSidebar"] button[kind="secondary"] {
    color: #999 !important;
    -webkit-text-fill-color: #999 !important;
    background: transparent !important;
}
/* Active nav button — same blue as brand */
section[data-testid="stSidebar"] button[kind="primary"] {
    color: #00d4ff !important;
    -webkit-text-fill-color: #00d4ff !important;
    background: #1a1a1a !important;
}
.stTabs [data-baseweb="tab-border"] {
    display: none !important;
}
.stTabs [data-baseweb="tab-highlight"] {
    display: none !important;
    background: transparent !important;
    height: 0 !important;
    border: none !important;
}
.stTabs [data-baseweb="tab-highlight"] > div {
    background: transparent !important;
    height: 0 !important;
    border: none !important;
}
/* Remove all possible underline effects */
.stTabs div[role="tab"][aria-selected="true"]::after {
    display: none !important;
    background: transparent !important;
    height: 0 !important;
}
.stTabs div[role="tab"][aria-selected="true"]::before {
    display: none !important;
    background: transparent !important;
    height: 0 !important;
}
.stTabs div[role="tab"]::after {
    display: none !important;
}
.stTabs div[role="tab"]::before {
    display: none !important;
}
/* Target any possible highlight elements */
.stTabs [data-baseweb="tab-highlight"],
.stTabs [data-baseweb="tab-highlight"] > div,
.stTabs [data-baseweb="tab-highlight"] > div > div {
    display: none !important;
    background: transparent !important;
    height: 0 !important;
    border: none !important;
    box-shadow: none !important;
}

/* Ticker strip */
.ticker {
    background: #111;
    border: 1px solid #222;
    padding: 14px 20px;
    display: flex;
    gap: 32px;
    margin-bottom: 20px;
    overflow-x: auto;
    font-family: 'JetBrains Mono', monospace;
}
.ticker-item {
    display: flex;
    align-items: baseline;
    gap: 8px;
    white-space: nowrap;
}
.ticker-item .label {
    color: #888;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 1px;
}
.ticker-item .value {
    font-size: 20px;
    font-weight: 700;
    color: #e0e0e0;
}
.ticker-item .delta {
    font-size: 11px;
    font-weight: 600;
}
.ticker-item .delta.up { color: #00d4ff; }
.ticker-item .delta.down { color: #ff4444; }

/* Panels */
.panel {
    background: #111;
    border: 1px solid #222;
    margin-bottom: 20px;
}
.panel-header {
    padding: 10px 16px;
    border-bottom: 1px solid #222;
    display: flex;
    align-items: center;
    justify-content: space-between;
}
.panel-header .title {
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    color: #888;
    font-family: 'JetBrains Mono', monospace;
}
.panel-header .status {
    font-size: 10px;
    padding: 2px 8px;
    border-radius: 2px;
    font-family: 'JetBrains Mono', monospace;
}
.panel-header .status.live {
    background: #00d4ff22;
    color: #00d4ff;
}
.panel-header .status.idle {
    background: #333;
    color: #666;
}
.panel-body {
    padding: 16px;
    font-family: 'JetBrains Mono', monospace;
}

/* Log output */
.log-output {
    font-family: 'JetBrains Mono', monospace;
    font-size: 12px;
    line-height: 1.8;
    max-height: 400px;
    overflow-y: auto;
    background: #0a0a0a;
    padding: 12px;
    border: 1px solid #222;
}
.log-output .time { color: #666; }
.log-output .ok { color: #00d4ff; }
.log-output .info { color: #888; }
.log-output .err { color: #ff4444; }
.log-output .skip { color: #ffaa00; }

/* Action bar */
.action-bar {
    background: #111;
    border: 1px solid #222;
    padding: 16px 20px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-top: 20px;
}
.action-bar .info {
    color: #888;
    font-size: 12px;
    font-family: 'JetBrains Mono', monospace;
}
.action-bar .info strong { color: #c8c8c8; }

/* Buttons */
.stButton > button,
.stFormSubmitButton > button {
    background: #00d4ff !important;
    color: #0a0a0a !important;
    border: none !important;
    padding: 10px 24px !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 12px !important;
    font-weight: 700 !important;
    text-transform: uppercase !important;
    letter-spacing: 1px !important;
    border-radius: 2px !important;
}
.stButton > button:hover,
.stFormSubmitButton > button:hover {
    background: #00b8db !important;
}
.stButton > button span,
.stFormSubmitButton > button span {
    color: #0a0a0a !important;
}
.stButton > button p,
.stFormSubmitButton > button p {
    color: #0a0a0a !important;
}
/* Hide form submit hint text */
div[data-testid="stForm"] small,
div[data-testid="stCaptionContainer"],
div[data-testid="stForm"] div[data-testid="stCaptionContainer"],
.stFormSubmitButton ~ div,
.stFormSubmitButton ~ small,
.stFormSubmitButton ~ span {
    display: none !important;
    visibility: hidden !important;
    height: 0 !important;
    overflow: hidden !important;
}

/* Hide password visibility toggle - remove from layout */
[data-testid="stTextInput"] button {
    display: none !important;
    width: 0 !important;
    padding: 0 !important;
    margin: 0 !important;
    position: absolute !important;
}

/* Make all input fields same size */
[data-testid="stTextInput"] > div > div {
    position: relative !important;
}
[data-testid="stTextInput"] input {
    width: 100% !important;
    padding-right: 12px !important;
}

/* Input fields - consistent sizing */
.stTextInput > div > div > input,
.stNumberInput > div > div > input {
    background: #1a1a1a;
    border: 1px solid #333;
    color: #e0e0e0;
    font-family: 'JetBrains Mono', monospace;
    border-radius: 2px;
    height: 40px !important;
    box-sizing: border-box !important;
}

/* Force all text inputs to same width */
.stTextInput {
    width: 100% !important;
}

/* Select box */
.stSelectbox > div > div {
    background: #1a1a1a;
    border: 1px solid #333;
    color: #e0e0e0;
    font-family: 'JetBrains Mono', monospace;
    border-radius: 2px;
}

/* Metrics */
.stMetric {
    background: #111;
    border: 1px solid #222;
    padding: 16px;
    border-radius: 2px;
}
.stMetric label {
    color: #555 !important;
    font-size: 11px !important;
    text-transform: uppercase;
    letter-spacing: 1px;
}
.stMetric [data-testid="stMetricValue"] {
    color: #e0e0e0 !important;
    font-size: 24px !important;
}
.stMetric [data-testid="stMetricDelta"] {
    font-size: 12px !important;
}

/* Chart bars */
.chart-bars {
    display: flex;
    align-items: flex-end;
    gap: 2px;
    height: 140px;
    padding: 10px 0;
}
.chart-bars .col {
    flex: 1;
    background: #00d4ff;
    min-height: 2px;
    border-radius: 1px 1px 0 0;
    opacity: 0.7;
}
.chart-bars .col:last-child { opacity: 1; }

/* Table */
.data-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 12px;
    font-family: 'JetBrains Mono', monospace;
}
.data-table th {
    text-align: left;
    padding: 8px 12px;
    color: #555;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 1px;
    font-size: 10px;
    border-bottom: 1px solid #222;
}
.data-table td {
    padding: 8px 12px;
    border-bottom: 1px solid #1a1a1a;
    color: #c8c8c8;
}
.data-table tr:hover td { background: #1a1a1a; }
.tag {
    font-size: 10px;
    padding: 2px 6px;
    border-radius: 2px;
    font-family: 'JetBrains Mono', monospace;
}
.tag.active { background: #00d4ff22; color: #00d4ff; }
.tag.paused { background: #ffaa0022; color: #ffaa00; }
.tag.idle { background: #333; color: #aaa; }

/* Streamlit alerts */
.stAlert {
    background: #111;
    border: 1px solid #222;
    border-radius: 2px;
    font-family: 'JetBrains Mono', monospace;
}
.stAlert > div {
    color: #c8c8c8;
}
.stAlert [data-testid="stMarkdownContainer"] p {
    color: #c8c8c8;
}

/* Hide Streamlit elements */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
.stDeployButton {display: none;}

/* Tabs */
/* Duplicate tab styles removed - using the first set */

/* Radio navigation */
.stRadio > div {
    display: flex;
    gap: 4px;
    background: #111;
    border: 1px solid #222;
    border-radius: 2px;
    padding: 8px 12px;
}
.stRadio > div > label {
    color: #888;
    font-family: 'JetBrains Mono', monospace;
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 1px;
    padding: 8px 16px;
    border-radius: 2px;
    cursor: pointer;
}
.stRadio > div > label:hover {
    color: #c8c8c8;
    background: #1a1a1a;
}
.stRadio > div > label[data-checked="true"] {
    color: #00d4ff;
    background: #1a1a1a;
}
.stTabs [data-baseweb="tab-highlight"] {
    background: #00d4ff;
}
/* Stop button - red when running */
button[key="stop_like"],
button[key="stop_follow"],
button[key="stop_unfollow"] {
    background: #ff4444 !important;
    border-color: #ff4444 !important;
}
button[key="stop_like"]:hover,
button[key="stop_follow"]:hover,
button[key="stop_unfollow"]:hover {
    background: #ff6666 !important;
    border-color: #ff6666 !important;
}
</style>
""", unsafe_allow_html=True)


# =============================================================
# SESSION STATE
# =============================================================

# Single account
if "handle" not in st.session_state:
    st.session_state.handle = ""

if "target" not in st.session_state:
    st.session_state.target = ""

if "verified" not in st.session_state:
    st.session_state.verified = False

if "profile_handle" not in st.session_state:
    st.session_state.profile_handle = ""

if "profile_followers" not in st.session_state:
    st.session_state.profile_followers = 0

if "client" not in st.session_state:
    st.session_state.client = None

if "bot_running" not in st.session_state:
    st.session_state.bot_running = False

# Per-bot running states (now managed by BotRunner)
# follow_bot_running, unfollow_bot_running - managed by runners
# follow_bot_stop, unfollow_bot_stop - managed by runners
# Log lines - managed by runners

# Verification results
if "verification_results" not in st.session_state:
    st.session_state.verification_results = []


# =============================================================
# LOADING SCREEN (first render — session state not yet restored)
# =============================================================

if "app_initialized" not in st.session_state:
    st.session_state.app_initialized = True
    st.markdown("""
    <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;height:60vh">
        <span style="color:#00d4ff;font-size:28px;font-weight:700;font-family:'JetBrains Mono',monospace;letter-spacing:-1px">bluesky-engine</span>
        <div style="color:#888;font-size:13px;margin-top:12px;font-family:'JetBrains Mono',monospace">Loading...</div>
        <div style="margin-top:20px;width:120px;height:3px;background:#222;border-radius:2px;overflow:hidden">
            <div style="width:40%;height:100%;background:#00d4ff;border-radius:2px;animation:pulse 1.2s ease-in-out infinite"></div>
        </div>
    </div>
    <style>
        @keyframes pulse {
            0% {transform:translateX(-100%)}
            100% {transform:translateX(350%)}
        }
    </style>
    """, unsafe_allow_html=True)
    st.rerun()

# =============================================================
# LOGIN PAGE (shown when not verified)
# =============================================================

if not st.session_state.verified:
    # Center the login form
    col1, col2, col3 = st.columns([5, 4, 5])

    with col2:
        # Brand header
        st.markdown("""
        <div style="text-align:center;margin-bottom:24px;margin-top:40px">
            <span style="color:#00d4ff;font-size:28px;font-weight:700;font-family:'JetBrains Mono',monospace;letter-spacing:-1px">bluesky-engine</span>
            <div style="color:#888;font-size:13px;margin-top:8px;font-family:'JetBrains Mono',monospace">Build Your Audience on Bluesky</div>
        </div>
        """, unsafe_allow_html=True)

        # Error message (if any)
        if st.session_state.get("login_error"):
            st.markdown(f"""
            <div style="padding:12px 16px;background:rgba(255,60,60,0.1);border:1px solid rgba(255,60,60,0.3);
                        border-radius:4px;margin-bottom:16px;font-size:13px;color:#ff6b6b;font-family:'JetBrains Mono',monospace">
                {st.session_state["login_error"]}
            </div>
            """, unsafe_allow_html=True)

        # Login form
        with st.form("login_form"):
            st.markdown('<span style="font-size:11px;text-transform:uppercase;letter-spacing:2px;color:#888">Handle</span>', unsafe_allow_html=True)
            st.text_input(
                "Handle",
                placeholder="alice.bsky.social",
                key="login_handle",
                label_visibility="collapsed",
            )

            st.markdown('<span style="font-size:11px;text-transform:uppercase;letter-spacing:2px;color:#888">App Password</span>', unsafe_allow_html=True)
            st.text_input(
                "App Password",
                type="password",
                placeholder="xxxx-xxxx-xxxx-xxxx",
                key="login_password",
                label_visibility="collapsed",
            )

            submitted = st.form_submit_button("SIGN IN", use_container_width=True, type="primary")

        # Trust message (always visible)
        st.markdown("""
        <div style="text-align:center;margin-top:24px;font-size:10px;color:#555;font-family:'JetBrains Mono',monospace">
            Your password is sent directly to Bluesky's servers. We never see or store it.
        </div>
        """, unsafe_allow_html=True)

        # Instructions (always visible)
        st.markdown("""
        <div style="margin-top:24px;font-size:14px;color:#888;line-height:1.8;font-family:'JetBrains Mono',monospace;display:flex;justify-content:center">
            <div style="text-align:left">
                <strong style="color:#c8c8c8">How to get an app password:</strong><br>
                1. Go to <a href="https://bsky.app/settings/app-passwords" target="_blank" style="color:#00d4ff">Settings > App Passwords</a> on bsky.app<br>
                2. Click "Add App Password" and enter a name<br>
                3. Copy and paste the password above
            </div>
        </div>
        """, unsafe_allow_html=True)

        if submitted:
            handle = st.session_state.login_handle.strip()
            password = st.session_state.login_password.strip()

            if not handle or not password:
                st.session_state["login_error"] = "Please enter both handle and app password."
                st.rerun()
            elif "." not in handle:
                st.session_state["login_error"] = f"Invalid handle '{handle}'. Use full format like alice.bsky.social"
                st.rerun()
            else:
                st.session_state["login_error"] = None
                try:
                    with st.spinner("Authenticating with Bluesky..."):
                        client = get_bluesky_client(handle, password)
                        profile = client.app.bsky.actor.get_profile({"actor": handle})
                    st.session_state.handle = handle
                    st.session_state.verified = True
                    st.session_state.client = client
                    st.session_state.profile_handle = profile.handle
                    st.session_state.profile_followers = profile.followers_count or 0
                    st.rerun()
                except AtProtocolError:
                    st.session_state["login_error"] = "Authentication failed. Check your handle and app password."
                    st.rerun()
                except Exception:
                    st.session_state["login_error"] = "Something went wrong. Please try again."
                    st.rerun()

    # Stop here - don't show the main app
    st.stop()


# =============================================================
# SIDEBAR NAVIGATION (shown only when verified)
# =============================================================

# Initialize active page
if "active_page" not in st.session_state:
    st.session_state.active_page = "DASHBOARD"

with st.sidebar:
    # Brand name
    version = get_version()
    st.markdown(f"""
    <div style="margin-bottom:32px">
        <span style="color:#00d4ff;font-size:14px;font-weight:700;font-family:'JetBrains Mono',monospace;letter-spacing:-0.5px">bluesky-engine</span>
        <span style="color:#555;font-size:14px;font-family:'JetBrains Mono',monospace"> {version}</span>
    </div>
    """, unsafe_allow_html=True)

    # Navigation buttons
    for nav_item in ["DASHBOARD", "LIKE", "FOLLOW", "UNFOLLOW"]:
        is_active = st.session_state.active_page == nav_item
        if st.button(
            nav_item,
            key=f"nav_{nav_item}",
            use_container_width=True,
            type="primary" if is_active else "secondary"
        ):
            st.session_state.active_page = nav_item
            st.rerun()

    # Disconnect button (aligned with nav buttons)
    if st.button("DISCONNECT", key="sidebar_disconnect", use_container_width=True):
        st.session_state.confirm_disconnect_sidebar = True

    if st.session_state.get("confirm_disconnect_sidebar"):
        st.warning("Disconnect?")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Yes", key="confirm_sidebar_yes", type="primary"):
                st.session_state.handle = ""
                st.session_state.verified = False
                st.session_state.client = None
                st.session_state.profile_handle = ""
                st.session_state.profile_followers = 0
                st.session_state.confirm_disconnect_sidebar = False
                st.rerun()
        with col2:
            if st.button("No", key="confirm_sidebar_no"):
                st.session_state.confirm_disconnect_sidebar = False
                st.rerun()

page = st.session_state.active_page


# =============================================================
# DASHBOARD TAB
# =============================================================

if page == "DASHBOARD":
    # Check if account is configured and verified
    if not st.session_state.verified:
        st.info("Please sign in to view dashboard.")
    else:
        # Show branded loading screen on first dashboard load after sign-in
        import time
        now = time.time()

        # Show loading screen if stats haven't been fetched yet
        if "cached_stats" not in st.session_state:
            st.markdown("""
            <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;height:60vh">
                <span style="color:#00d4ff;font-size:28px;font-weight:700;font-family:'JetBrains Mono',monospace;letter-spacing:-1px">bluesky-engine</span>
                <div style="color:#888;font-size:13px;margin-top:12px;font-family:'JetBrains Mono',monospace">Fetching your data...</div>
                <div style="margin-top:20px;width:120px;height:3px;background:#222;border-radius:2px;overflow:hidden">
                    <div style="width:40%;height:100%;background:#00d4ff;border-radius:2px;animation:pulse 1.2s ease-in-out infinite"></div>
                </div>
            </div>
            <style>
                @keyframes pulse {
                    0% {transform:translateX(-100%)}
                    100% {transform:translateX(350%)}
                }
            </style>
            """, unsafe_allow_html=True)

            # Fetch stats in background
            try:
                client = st.session_state.client
                stats = get_stats(st.session_state.handle, client)
                st.session_state.cached_stats = stats
                st.rerun()
            except Exception:
                st.error("Failed to fetch stats. Please try again.")
                st.stop()

        # Fetch stats for the account (cached in session state)
        try:

            if "cached_stats" in st.session_state:
                stats = st.session_state.cached_stats
            else:
                with st.spinner("Fetching stats..."):
                    client = st.session_state.client
                    stats = get_stats(st.session_state.handle, client)
                st.session_state.cached_stats = stats

            followers = stats["followers"]
            following = stats["following"]
            posts_per_day = stats["posts_per_day"]
            engagement_rate = stats["engagement_rate"]
            reply_rate = stats["reply_rate"]
            repost_rate = stats["repost_rate"]
            avg_replies_per_post = stats["avg_replies_per_post"]
            growth_rate_7d = stats["growth_rate_7d"]
            follow_ratio = stats["follow_ratio"]
            non_followers = stats["non_followers"]

            # Calculate follow-back rate
            follow_back_rate = (followers / following * 100) if following > 0 else 0

            # Determine colors
            if follow_back_rate >= 20:
                fbr_color = "#4ade80"
            elif follow_back_rate >= 10:
                fbr_color = "#fbbf24"
            else:
                fbr_color = "#f87171"

            if engagement_rate >= 5:
                er_color = "#4ade80"
            elif engagement_rate >= 2:
                er_color = "#fbbf24"
            else:
                er_color = "#f87171"

            # Save snapshot
            save_snapshot(followers, following)

            # Request notification permission (once per session)
            if not st.session_state.get("notification_requested"):
                components.html("""
                <script>
                if ("Notification" in window && Notification.permission === "default") {
                    Notification.requestPermission();
                }
                </script>
                """, height=0)
                st.session_state.notification_requested = True

            # Contextual guidance for edge cases
            if followers == 0:
                st.info("Your account has no followers yet. Use the FOLLOW tab to start growing.")
            elif non_followers > following * 0.8 and following > 100:
                st.markdown(f"""
                <div style="padding:10px 16px;background:#1a1500;border:1px solid #333;border-left:3px solid #ff8800;border-radius:4px;margin-bottom:16px;font-size:12px;color:#c8c8c8;font-family:'JetBrains Mono',monospace">
                    High non-follower ratio ({non_followers:,} of {following:,}). Consider running the UNFOLLOW bot to clean up.
                </div>
                """, unsafe_allow_html=True)

            # ─── SUCCESS METRICS ─────────────────────────────
            st.markdown("""
            <div style="margin-bottom:16px;margin-top:8px">
                <span style="font-size:14px;text-transform:uppercase;letter-spacing:2px;color:#00d4ff;font-family:'JetBrains Mono',monospace;font-weight:600">Success Metrics</span>
                <span style="font-size:14px;color:#555;margin-left:12px;font-family:'JetBrains Mono',monospace">Are we winning?</span>
            </div>
            """, unsafe_allow_html=True)

            col1, col2, col3, col4 = st.columns(4)

            with col1:
                st.markdown(f"""
                <div style="background:#111;border:1px solid #222;border-radius:4px;padding:32px;text-align:center">
                    <div style="font-size:12px;color:#999;text-transform:uppercase;letter-spacing:1px;margin-bottom:12px">
                        Followers <span style="cursor:help;color:#666;font-size:10px;vertical-align:super" data-tooltip="Total accounts following you">ⓘ</span>
                    </div>
                    <div style="font-size:40px;font-weight:700;color:#c8c8c8">{followers:,}</div>
                    <div style="font-size:12px;color:#4ade80;margin-top:8px">+{growth_rate_7d}/day avg</div>
                </div>
                """, unsafe_allow_html=True)

            with col2:
                st.markdown(f"""
                <div style="background:#111;border:1px solid #222;border-radius:4px;padding:32px;text-align:center">
                    <div style="font-size:12px;color:#999;text-transform:uppercase;letter-spacing:1px;margin-bottom:12px">
                        Growth Rate <span style="cursor:help;color:#666;font-size:10px;vertical-align:super" data-tooltip="Average new followers per day over the last 7 days">ⓘ</span>
                    </div>
                    <div style="font-size:40px;font-weight:700;color:#4ade80">{growth_rate_7d}</div>
                    <div style="font-size:12px;color:#666;margin-top:8px">followers/day</div>
                </div>
                """, unsafe_allow_html=True)

            with col3:
                st.markdown(f"""
                <div style="background:#111;border:1px solid #222;border-radius:4px;padding:32px;text-align:center">
                    <div style="font-size:12px;color:#999;text-transform:uppercase;letter-spacing:1px;margin-bottom:12px">
                        Follow Ratio <span style="cursor:help;color:#666;font-size:10px;vertical-align:super" data-tooltip="Followers ÷ Following. Higher = more credible account">ⓘ</span>
                    </div>
                    <div style="font-size:40px;font-weight:700;color:#c8c8c8">{follow_ratio:.1f}x</div>
                    <div style="font-size:12px;color:#666;margin-top:8px">followers/following</div>
                </div>
                """, unsafe_allow_html=True)

            with col4:
                st.markdown(f"""
                <div style="background:#111;border:1px solid #222;border-radius:4px;padding:32px;text-align:center">
                    <div style="font-size:12px;color:#999;text-transform:uppercase;letter-spacing:1px;margin-bottom:12px">
                        Engagement <span style="cursor:help;color:#666;font-size:10px;vertical-align:super" data-tooltip="Average engagement (likes, replies, reposts) per post as % of followers">ⓘ</span>
                    </div>
                    <div style="font-size:40px;font-weight:700;color:{er_color}">{engagement_rate}%</div>
                    <div style="font-size:12px;color:#666;margin-top:8px">of followers</div>
                </div>
                """, unsafe_allow_html=True)

            # ─── KEY DRIVERS ──────────────────────────────────
            st.markdown("""
            <div style="margin-bottom:16px;margin-top:24px">
                <span style="font-size:14px;text-transform:uppercase;letter-spacing:2px;color:#00d4ff;font-family:'JetBrains Mono',monospace;font-weight:600">Key Drivers</span>
                <span style="font-size:14px;color:#555;margin-left:12px;font-family:'JetBrains Mono',monospace">What do we change?</span>
            </div>
            """, unsafe_allow_html=True)

            col5, col6, col7, col8 = st.columns(4)

            with col5:
                st.markdown(f"""
                <div style="background:#111;border:1px solid #222;border-radius:4px;padding:28px;text-align:center">
                    <div style="font-size:12px;color:#999;text-transform:uppercase;letter-spacing:1px;margin-bottom:10px">
                        Posts/Day <span style="cursor:help;color:#666;font-size:10px;vertical-align:super" data-tooltip="Average posts per day. More posts = more engagement opportunities">ⓘ</span>
                    </div>
                    <div style="font-size:32px;font-weight:700;color:#c8c8c8">{posts_per_day}</div>
                </div>
                """, unsafe_allow_html=True)

            with col6:
                st.markdown(f"""
                <div style="background:#111;border:1px solid #222;border-radius:4px;padding:28px;text-align:center">
                    <div style="font-size:12px;color:#999;text-transform:uppercase;letter-spacing:1px;margin-bottom:10px">
                        Follow-back Rate <span style="cursor:help;color:#666;font-size:10px;vertical-align:super" data-tooltip="% of accounts you follow who follow you back. Optimize who you follow">ⓘ</span>
                    </div>
                    <div style="font-size:32px;font-weight:700;color:{fbr_color}">{follow_back_rate:.1f}%</div>
                </div>
                """, unsafe_allow_html=True)

            with col7:
                st.markdown(f"""
                <div style="background:#111;border:1px solid #222;border-radius:4px;padding:28px;text-align:center">
                    <div style="font-size:12px;color:#999;text-transform:uppercase;letter-spacing:1px;margin-bottom:10px">
                        Reply Rate <span style="cursor:help;color:#666;font-size:10px;vertical-align:super" data-tooltip="Replies as % of total engagement. Higher = deeper conversations">ⓘ</span>
                    </div>
                    <div style="font-size:32px;font-weight:700;color:#c8c8c8">{reply_rate}%</div>
                </div>
                """, unsafe_allow_html=True)

            with col8:
                st.markdown(f"""
                <div style="background:#111;border:1px solid #222;border-radius:4px;padding:28px;text-align:center">
                    <div style="font-size:12px;color:#999;text-transform:uppercase;letter-spacing:1px;margin-bottom:10px">
                        Repost Rate <span style="cursor:help;color:#666;font-size:10px;vertical-align:super" data-tooltip="Reposts as % of total engagement. Higher = content spreading">ⓘ</span>
                    </div>
                    <div style="font-size:32px;font-weight:700;color:#c8c8c8">{repost_rate}%</div>
                </div>
                """, unsafe_allow_html=True)

        except Exception as e:
            st.error(f"Failed to fetch stats: {str(e)[:200]}")


# =============================================================
# LIKE TAB
# =============================================================

if page == "LIKE":
    st.markdown("""
    <div style="margin-bottom:20px">
        <span style="font-size:11px;text-transform:uppercase;letter-spacing:2px;color:#888">Like Bot</span>
        <br>
        <span style="font-size:13px;color:#888">Like posts from non-followers randomly to get their attention</span>
    </div>
    """, unsafe_allow_html=True)

    # Check if account is configured
    if not st.session_state.verified:
        st.warning("Please sign in first.")
    else:
        # Config
        col1, col2, col3, col4, col5 = st.columns(5)

        with col1:
            batch_size = st.number_input("BATCH SIZE", min_value=10, max_value=500, value=300, step=10,
                help="Number of non-followers to like per run. Start with 50 to test.")
        with col2:
            likes_per_user = st.number_input("LIKES PER USER", min_value=1, max_value=5, value=2, step=1,
                help="How many posts to like per person. 2 is recommended.")
        with col3:
            daily_cap = st.number_input("DAILY CAP", min_value=10, max_value=1000, value=800, step=10, key="like_daily_cap",
                help="Maximum likes per day across all runs. Helps avoid rate limits.")
        with col4:
            delay_min = st.number_input("MIN DELAY (sec)", min_value=1, max_value=60, value=5, step=1,
                help="Minimum seconds between likes. Lower = faster but riskier.")
        with col5:
            delay_max = st.number_input("MAX DELAY (sec)", min_value=1, max_value=60, value=10, step=1,
                help="Maximum seconds between likes. Random delay between min and max.")

        # Get runner reference
        runner = st.session_state.like_runner

        # Toggle button - changes between RUN and STOP
        col_btn, col_info = st.columns([1, 3])

        # Toggle button - changes between RUN and STOP
        if runner.running:
            # Bot is running - show STOP button
            if st.button("⏹ STOP", key="stop_like", use_container_width=True, type="primary"):
                runner.stop()
                st.rerun()
        else:
            # Bot is stopped - show RUN button
            run_clicked = st.button("▶ RUN LIKE", key="run_like", use_container_width=True)

        # Live log
        status_class = "live" if runner.running else "idle"
        status_label = "LIVE" if runner.running else "IDLE"
        st.markdown(f"""
        <div class="panel" style="margin-top:20px">
            <div class="panel-header">
                <span class="title">Live Output</span>
                <span class="status {status_class}">{status_label}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        log_placeholder = st.empty()

        # Run the bot (when RUN button clicked)
        if not runner.running and run_clicked:
            # Check if another bot is running
            if any_bot_running():
                running_bot = get_running_bot_name()
                st.error(f"Cannot start Like Bot — {running_bot} Bot is already running. Stop it first or wait for it to finish.")
            # Validate delays
            elif delay_min > delay_max:
                st.error("Min delay must be <= max delay")
            else:
                # Start bot in background thread
                account = [{"handle": st.session_state.handle, "client": st.session_state.get("client"), "enabled": True}]
                # Store settings for retry
                st.session_state.like_settings = {
                    "account": account,
                    "batch_size": batch_size,
                    "likes_per_user": likes_per_user,
                    "delay_min": delay_min,
                    "delay_max": delay_max,
                }
                runner.start(
                    like_bot_run,
                    account,
                    batch_size,
                    likes_per_user,
                    delay_min,
                    delay_max,
                )
                st.rerun()

        # Bot is running - show logs with auto-refresh fragment
        if runner.running:
            live_log_panel(runner)

        # Bot finished - show results
        if not runner.running:
            # Check for results
            results = runner.get_results()
            error = runner.get_error()

            if error:
                error_msg = error.lower()
                if "auth" in error_msg or "invalid" in error_msg or "password" in error_msg:
                    st.error(f"Authentication failed: {error}. Check your credentials in SETTINGS.")
                elif "rate" in error_msg or "429" in error_msg:
                    st.error(f"Rate limited: {error}. Wait a few minutes and try again.")
                elif "timeout" in error_msg or "connection" in error_msg:
                    st.error(f"Network error: {error}. Check your connection and try again.")
                else:
                    st.error(f"Bot error: {error}")
                # Retry button
                if st.button("🔄 RETRY", key="retry_like"):
                    settings = st.session_state.get("like_settings", {})
                    if settings:
                        runner.start(
                            like_bot_run,
                            settings["account"],
                            settings["batch_size"],
                            settings["likes_per_user"],
                            settings["delay_min"],
                            settings["delay_max"],
                        )
                        st.rerun()
                else:
                    runner.clear()
            elif results:
                total_liked = sum(r["liked"] for r in results)
                total_skipped = sum(r["skipped"] for r in results)
                total_errors = sum(r["errors"] for r in results)
                if runner.stop_requested:
                    st.warning(f"Like bot stopped: {total_liked} liked, {total_skipped} skipped, {total_errors} errors")
                    send_notification("bluesky-engine", f"Like bot stopped — {total_liked} liked")
                else:
                    st.success(f"Like bot complete: {total_liked} liked, {total_skipped} skipped, {total_errors} errors")
                    send_notification("bluesky-engine", f"Like bot complete — {total_liked} liked, {total_skipped} skipped")
                runner.clear()

            # Show existing log
            logs = runner.get_logs()
            if logs:
                log_text = "\n".join(logs[-50:])
                log_placeholder.code(log_text, language="bash")
            else:
                log_placeholder.code("Waiting to start...", language="bash")


# =============================================================
# FOLLOW TAB (Placeholder)
# =============================================================

if page == "FOLLOW":
    st.markdown("""
    <div style="margin-bottom:20px">
        <span style="font-size:11px;text-transform:uppercase;letter-spacing:2px;color:#888">Follow Bot</span>
        <br>
        <span style="font-size:13px;color:#888">Build your audience by following relevant accounts</span>
    </div>
    """, unsafe_allow_html=True)

    # Check if account is configured
    if not st.session_state.verified:
        st.warning("Please sign in first.")
    else:
        # Show account with target input
        st.markdown("""
        <div style="margin-bottom:10px">
            <span style="font-size:11px;text-transform:uppercase;letter-spacing:2px;color:#888">Assign Target Account</span>
        </div>
        """, unsafe_allow_html=True)

        # Target input
        target = st.text_input(
            "TARGET ACCOUNT",
            value=st.session_state.target,
            placeholder="karpathy.bsky.social",
            key="follow_target",
        )
        st.session_state.target = target

        # Config
        st.markdown("""
        <div style="margin-top:20px;margin-bottom:10px">
            <span style="font-size:11px;text-transform:uppercase;letter-spacing:2px;color:#888">Bot Settings</span>
        </div>
        """, unsafe_allow_html=True)

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            pull_limit = st.number_input("PULL LIMIT", min_value=10, max_value=500, value=300, step=10,
                help="Max followers to pull from target account. 200 is a good start.")
        with col2:
            daily_cap = st.number_input("DAILY CAP", min_value=10, max_value=200, value=150, step=5,
                help="Max follows per account per run. Keeps you under rate limits.")
        with col3:
            follow_delay_min = st.number_input("MIN DELAY (sec)", min_value=1, max_value=60, value=5, step=1, key="follow_delay_min",
                help="Minimum seconds between follows. Lower = faster but riskier.")
        with col4:
            follow_delay_max = st.number_input("MAX DELAY (sec)", min_value=1, max_value=60, value=15, step=1, key="follow_delay_max",
                help="Maximum seconds between follows. Random delay between min and max.")

        auto_like = st.checkbox("Auto-like posts after following", value=True)

        # Get runner reference
        runner = st.session_state.follow_runner

        # Toggle button - changes between RUN and STOP
        if runner.running:
            # Bot is running - show STOP button
            if st.button("⏹ STOP", key="stop_follow", use_container_width=True, type="primary"):
                runner.stop()
                st.rerun()
        else:
            # Bot is stopped - show RUN button
            follow_run_clicked = st.button("▶ RUN FOLLOW", key="run_follow", use_container_width=True)

        # Live log
        status_class = "live" if runner.running else "idle"
        status_label = "LIVE" if runner.running else "IDLE"
        st.markdown(f"""
        <div class="panel" style="margin-top:20px">
            <div class="panel-header">
                <span class="title">Live Output</span>
                <span class="status {status_class}">{status_label}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        follow_log_placeholder = st.empty()

        # Run the bot (when RUN button clicked)
        if not runner.running and follow_run_clicked:
            # Check if another bot is running
            if any_bot_running():
                running_bot = get_running_bot_name()
                st.error(f"Cannot start Follow Bot — {running_bot} Bot is already running. Stop it first or wait for it to finish.")
            # Validate delays
            elif follow_delay_min > follow_delay_max:
                st.error("Min delay must be <= max delay")
            else:
                # Validate target
                target = st.session_state.target.strip()
                if not target:
                    st.error("No target configured. Add a target account.")
                elif "." not in target:
                    st.error(f"Invalid target @{target}. Must be a full handle like 'karpathy.bsky.social'")
                else:
                    # Start bot in background thread
                    valid_accounts = [{
                        "handle": st.session_state.handle,
                        "client": st.session_state.get("client"),
                        "target": target,
                        "enabled": True
                    }]
                    # Store settings for retry
                    st.session_state.follow_settings = {
                        "accounts": valid_accounts,
                        "pull_limit": pull_limit,
                        "daily_cap": daily_cap,
                        "delay_min": follow_delay_min,
                        "delay_max": follow_delay_max,
                        "auto_like": auto_like,
                    }
                    runner.start(
                        follow_bot_run,
                        valid_accounts,
                        pull_limit,
                        daily_cap,
                        follow_delay_min,
                        follow_delay_max,
                        auto_like,
                    )
                    st.rerun()

        # Bot is running - show logs with auto-refresh fragment
        if runner.running:
            live_log_panel(runner)

        # Bot finished - show results
        if not runner.running:
            # Check for results
            results = runner.get_results()
            error = runner.get_error()

            if error:
                error_msg = error.lower()
                if "auth" in error_msg or "invalid" in error_msg or "password" in error_msg:
                    st.error(f"Authentication failed: {error}. Check your credentials in SETTINGS.")
                elif "rate" in error_msg or "429" in error_msg:
                    st.error(f"Rate limited: {error}. Wait a few minutes and try again.")
                elif "timeout" in error_msg or "connection" in error_msg:
                    st.error(f"Network error: {error}. Check your connection and try again.")
                else:
                    st.error(f"Bot error: {error}")
                # Retry button
                if st.button("🔄 RETRY", key="retry_follow"):
                    settings = st.session_state.get("follow_settings", {})
                    if settings:
                        runner.start(
                            follow_bot_run,
                            settings["accounts"],
                            settings["pull_limit"],
                            settings["daily_cap"],
                            settings["delay_min"],
                            settings["delay_max"],
                            settings["auto_like"],
                        )
                        st.rerun()
                else:
                    runner.clear()
            elif results:
                total_followed = sum(r["followed"] for r in results)
                total_liked = sum(r["liked"] for r in results)
                total_errors = sum(r["errors"] for r in results)
                if runner.stop_requested:
                    st.warning(f"Follow bot stopped: {total_followed} followed, {total_liked} liked, {total_errors} errors")
                    send_notification("bluesky-engine", f"Follow bot stopped — {total_followed} followed")
                else:
                    st.success(f"Follow bot complete: {total_followed} followed, {total_liked} liked, {total_errors} errors")
                    send_notification("bluesky-engine", f"Follow bot complete — {total_followed} followed, {total_liked} liked")
                runner.clear()

            # Show existing log
            logs = runner.get_logs()
            if logs:
                log_text = "\n".join(logs[-50:])
                follow_log_placeholder.code(log_text, language="bash")
            else:
                follow_log_placeholder.code("Waiting to start...", language="bash")


# =============================================================
# UNFOLLOW TAB (Placeholder)
# =============================================================

if page == "UNFOLLOW":
    st.markdown("""
    <div style="margin-bottom:20px">
        <span style="font-size:11px;text-transform:uppercase;letter-spacing:2px;color:#888">Unfollow Bot</span>
        <br>
        <span style="font-size:13px;color:#888">Unfollow non-followers older than X days</span>
    </div>
    """, unsafe_allow_html=True)

    # Check if account is configured
    if not st.session_state.verified:
        st.warning("Please sign in first.")
    else:
        # Settings
        st.markdown("""
        <div style="margin-bottom:10px">
            <span style="font-size:11px;text-transform:uppercase;letter-spacing:2px;color:#888">Settings</span>
        </div>
        """, unsafe_allow_html=True)

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            days_threshold = st.number_input("DAYS THRESHOLD", min_value=1, max_value=365, value=30, step=1,
                help="Only unfollow if followed more than X days ago. 30 is recommended.")
        with col2:
            daily_cap = st.number_input("DAILY CAP", min_value=10, max_value=300, value=200, step=5,
                key="unfollow_daily_cap", help="Max unfollows per run. Keeps you under rate limits.")
        with col3:
            unfollow_delay_min = st.number_input("MIN DELAY (sec)", min_value=1, max_value=60, value=5, step=1,
                key="unfollow_delay_min", help="Minimum seconds between unfollows.")
        with col4:
            unfollow_delay_max = st.number_input("MAX DELAY (sec)", min_value=1, max_value=60, value=15, step=1,
                key="unfollow_delay_max", help="Maximum seconds between unfollows.")

        # Exemptions
        st.markdown("""
        <div style="margin-top:20px;margin-bottom:10px">
            <span style="font-size:11px;text-transform:uppercase;letter-spacing:2px;color:#888">Exemptions</span>
            <span style="font-size:12px;color:#888;margin-left:10px">Accounts to never unfollow (one per line)</span>
        </div>
        """, unsafe_allow_html=True)

        exemptions_text = st.text_area(
            "EXEMPTIONS",
            value="",
            height=100,
            key="unfollow_exemptions",
            label_visibility="collapsed",
            placeholder="karpathy.bsky.social\nbsky.app",
        )
        exemptions = [e.strip() for e in exemptions_text.split("\n") if e.strip()]

        # Get runner reference
        runner = st.session_state.unfollow_runner

        # Preview button (always available)
        col_preview, col_run, col_info = st.columns([1, 1, 2])

        with col_preview:
            preview_clicked = st.button("👁 PREVIEW", key="preview_unfollow", use_container_width=True)

        with col_run:
            if runner.running:
                # Bot is running - show STOP button
                if st.button("⏹ STOP", key="stop_unfollow", use_container_width=True, type="primary"):
                    runner.stop()
                    st.rerun()
            else:
                # Bot is stopped - show RUN button
                unfollow_clicked = st.button("🚪 RUN UNFOLLOW", key="run_unfollow", use_container_width=True)

        # Preview results
        if preview_clicked:
            st.markdown("""
            <div style="margin-top:20px;margin-bottom:10px">
                <span style="font-size:11px;text-transform:uppercase;letter-spacing:2px;color:#888">Preview</span>
            </div>
            """, unsafe_allow_html=True)

            # Create single account list for preview
            account = [{"handle": st.session_state.handle, "client": st.session_state.get("client"), "enabled": True}]

            with st.spinner("Fetching preview data..."):
                preview_results = get_unfollow_preview(account, days_threshold, exemptions)

            for r in preview_results:
                if "error" in r:
                    st.error(f"@{r['handle']}: {r['error']}")
                else:
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric(f"@{r['handle']}", f"{r['eligible']} eligible")
                    with col2:
                        st.metric("Following", f"{r['total_following']:,}")
                    with col3:
                        st.metric("Followers", f"{r['total_followers']:,}")
                    with col4:
                        st.metric("Non-followers", f"{r['non_followers']:,}")

        # Live log
        status_class = "live" if runner.running else "idle"
        status_label = "LIVE" if runner.running else "IDLE"
        st.markdown(f"""
        <div class="panel" style="margin-top:20px">
            <div class="panel-header">
                <span class="title">Live Output</span>
                <span class="status {status_class}">{status_label}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        unfollow_log_placeholder = st.empty()

        # Run the bot (when RUN button clicked)
        if not runner.running and unfollow_clicked:
            st.session_state.confirm_unfollow = True

        # Confirmation dialog for unfollow
        if st.session_state.get("confirm_unfollow") and not runner.running:
            st.warning(f"⚠️ About to unfollow non-followers older than {days_threshold} days (up to {daily_cap} per run). This action is irreversible.")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Yes, start unfollow", key="confirm_unfollow_yes", type="primary"):
                    st.session_state.confirm_unfollow = False
                    # Check if another bot is running
                    if any_bot_running():
                        running_bot = get_running_bot_name()
                        st.error(f"Cannot start Unfollow Bot — {running_bot} Bot is already running. Stop it first or wait for it to finish.")
                    # Validate delays
                    elif unfollow_delay_min > unfollow_delay_max:
                        st.error("Min delay must be <= max delay")
                    else:
                        # Start bot in background thread
                        account = [{"handle": st.session_state.handle, "client": st.session_state.get("client"), "enabled": True}]
                        # Store settings for retry
                        st.session_state.unfollow_settings = {
                            "account": account,
                            "days_threshold": days_threshold,
                            "daily_cap": daily_cap,
                            "delay_min": unfollow_delay_min,
                            "delay_max": unfollow_delay_max,
                            "exemptions": exemptions,
                        }
                        runner.start(
                            unfollow_bot_run,
                            account,
                            days_threshold,
                            daily_cap,
                            unfollow_delay_min,
                            unfollow_delay_max,
                            exemptions,
                        )
                        st.rerun()
            with col2:
                if st.button("Cancel", key="confirm_unfollow_no"):
                    st.session_state.confirm_unfollow = False
                    st.rerun()

        # Bot is running - show logs with auto-refresh fragment
        if runner.running:
            live_log_panel(runner)

        # Bot finished - show results
        if not runner.running:
            # Check for results
            results = runner.get_results()
            error = runner.get_error()

            if error:
                error_msg = error.lower()
                if "auth" in error_msg or "invalid" in error_msg or "password" in error_msg:
                    st.error(f"Authentication failed: {error}. Check your credentials in SETTINGS.")
                elif "rate" in error_msg or "429" in error_msg:
                    st.error(f"Rate limited: {error}. Wait a few minutes and try again.")
                elif "timeout" in error_msg or "connection" in error_msg:
                    st.error(f"Network error: {error}. Check your connection and try again.")
                else:
                    st.error(f"Bot error: {error}")
                # Retry button
                if st.button("🔄 RETRY", key="retry_unfollow"):
                    settings = st.session_state.get("unfollow_settings", {})
                    if settings:
                        runner.start(
                            unfollow_bot_run,
                            settings["account"],
                            settings["days_threshold"],
                            settings["daily_cap"],
                            settings["delay_min"],
                            settings["delay_max"],
                            settings["exemptions"],
                        )
                        st.rerun()
                else:
                    runner.clear()
            elif results:
                total_unfollowed = sum(r["unfollowed"] for r in results)
                total_skipped = sum(r["skipped"] for r in results)
                total_errors = sum(r["errors"] for r in results)
                if runner.stop_requested:
                    st.warning(f"Unfollow bot stopped: {total_unfollowed} unfollowed, {total_skipped} skipped, {total_errors} errors")
                    send_notification("bluesky-engine", f"Unfollow bot stopped — {total_unfollowed} unfollowed")
                else:
                    st.success(f"Unfollow bot complete: {total_unfollowed} unfollowed, {total_skipped} skipped, {total_errors} errors")
                    send_notification("bluesky-engine", f"Unfollow bot complete — {total_unfollowed} unfollowed, {total_skipped} skipped")
                runner.clear()

            # Show existing log
            logs = runner.get_logs()
            if logs:
                log_text = "\n".join(logs[-50:])
                unfollow_log_placeholder.code(log_text, language="bash")
            else:
                unfollow_log_placeholder.code("Waiting to start...", language="bash")
