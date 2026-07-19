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

from utils.auth import login
from utils.stats import get_stats
from utils.tracker import load_history, save_snapshot, get_chart_data
from bots.like_bot import like_bot_run
from bots.follow_bot import follow_bot_run
from bots.unfollow_bot import unfollow_bot_run, get_unfollow_preview


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


# =============================================================
# PAGE CONFIG
# =============================================================

st.set_page_config(
    page_title="BSKY_GROWTH",
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

/* Topbar */
/* Sidebar - matches mockup 18-nav-sidebar.html */
[data-testid="stSidebar"] {
    background: #111;
    border-right: 1px solid #222;
    padding: 20px 16px;
}
/* Hide collapse button - sidebar always visible */
[data-testid="stSidebarCollapseButton"] {
    display: none !important;
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
    text-align: left !important;
    justify-content: flex-start !important;
}
section[data-testid="stSidebar"] button[kind="secondary"] p,
section[data-testid="stSidebar"] button[kind="primary"] p,
section[data-testid="stSidebar"] button[kind="tertiary"] p,
section[data-testid="stSidebar"] button[kind="secondary"] span,
section[data-testid="stSidebar"] button[kind="primary"] span,
section[data-testid="stSidebar"] button[kind="tertiary"] span {
    font-size: 12px !important;
    text-align: left !important;
    text-align: left !important;
    justify-content: flex-start !important;
    border-radius: 2px !important;
    transition: all 0.15s ease !important;
    width: 100% !important;
    margin-bottom: 4px !important;
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
.stButton > button {
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
.stButton > button:hover {
    background: #00b8db !important;
}
.stButton > button span {
    color: #0a0a0a !important;
}
.stButton > button p {
    color: #0a0a0a !important;
}

/* Input fields */
.stTextInput > div > div > input,
.stNumberInput > div > div > input {
    background: #1a1a1a;
    border: 1px solid #333;
    color: #e0e0e0;
    font-family: 'JetBrains Mono', monospace;
    border-radius: 2px;
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
header {visibility: hidden;}
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
}
.stTabs [data-baseweb="tab-highlight"] {
    background: #00d4ff;
}
</style>
""", unsafe_allow_html=True)


# =============================================================
# SESSION STATE
# =============================================================

# Single account
if "handle" not in st.session_state:
    st.session_state.handle = ""

if "password" not in st.session_state:
    st.session_state.password = ""

if "target" not in st.session_state:
    st.session_state.target = ""

if "verified" not in st.session_state:
    st.session_state.verified = False

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
# SIDEBAR NAVIGATION
# =============================================================

# Initialize active page
if "active_page" not in st.session_state:
    st.session_state.active_page = "DASHBOARD"

with st.sidebar:
    # Brand name
    version = get_version()
    st.markdown(f"""
    <div style="margin-bottom:32px">
        <span style="color:#00d4ff;font-size:14px;font-weight:700;font-family:'JetBrains Mono',monospace;letter-spacing:-0.5px">bsky_growth</span>
        <span style="color:#555;font-size:14px;font-family:'JetBrains Mono',monospace"> {version}</span>
    </div>
    """, unsafe_allow_html=True)

    # Navigation buttons - same style as SAVE & VERIFY button
    for nav_item in ["DASHBOARD", "LIKE", "FOLLOW", "UNFOLLOW", "SETTINGS"]:
        is_active = st.session_state.active_page == nav_item
        if st.button(
            nav_item,
            key=f"nav_{nav_item}",
            use_container_width=True,
            type="primary" if is_active else "secondary"
        ):
            st.session_state.active_page = nav_item
            st.rerun()

page = st.session_state.active_page


# =============================================================
# DASHBOARD TAB
# =============================================================

if page == "DASHBOARD":
    # Check if account is configured and verified
    if not st.session_state.handle or not st.session_state.password:
        st.info("Configure your account in the SETTINGS tab to see live stats here.")
    elif not st.session_state.verified:
        st.info("Please verify your account in the SETTINGS tab first.")
    else:
        # Fetch stats for the account
        try:
            from utils.auth import login
            from utils.stats import get_stats

            with st.spinner("Fetching stats..."):
                client = login(st.session_state.handle, st.session_state.password)
                stats = get_stats(st.session_state.handle, client)

            followers = stats["followers"]
            following = stats["following"]
            ratio = stats["ratio"]
            non_followers = following - followers

            # Calculate follow-back rate
            follow_back_rate = (followers / following * 100) if following > 0 else 0

            # Determine follow-back rate color
            if follow_back_rate >= 20:
                fbr_color = "#4ade80"  # green
            elif follow_back_rate >= 10:
                fbr_color = "#fbbf24"  # yellow
            else:
                fbr_color = "#f87171"  # red

            # Calculate growth rate from history
            history = load_history()
            chart_data = get_chart_data(history)
            growth_rate = 0
            if len(chart_data) >= 2:
                days_tracked = len(chart_data)
                total_growth = chart_data[-1]["followers"] - chart_data[0]["followers"]
                growth_rate = total_growth / days_tracked if days_tracked > 0 else 0

            # Save snapshot
            save_snapshot(followers, following)

            # Dashboard cards - one metric per card (6 cards in 2 rows)
            # Row 1
            col1, col2, col3 = st.columns(3)

            with col1:
                st.markdown(f"""
                <div style="background:#111;border:1px solid #222;border-radius:4px;padding:20px;text-align:center">
                    <div style="font-size:11px;color:#888;text-transform:uppercase;letter-spacing:1px;margin-bottom:8px">Followers</div>
                    <div style="font-size:24px;font-weight:700;color:#c8c8c8">{followers:,}</div>
                </div>
                """, unsafe_allow_html=True)

            with col2:
                st.markdown(f"""
                <div style="background:#111;border:1px solid #222;border-radius:4px;padding:20px;text-align:center">
                    <div style="font-size:11px;color:#888;text-transform:uppercase;letter-spacing:1px;margin-bottom:8px">Following</div>
                    <div style="font-size:24px;font-weight:700;color:#c8c8c8">{following:,}</div>
                </div>
                """, unsafe_allow_html=True)

            with col3:
                st.markdown(f"""
                <div style="background:#111;border:1px solid #222;border-radius:4px;padding:20px;text-align:center">
                    <div style="font-size:11px;color:#888;text-transform:uppercase;letter-spacing:1px;margin-bottom:8px">Ratio</div>
                    <div style="font-size:24px;font-weight:700;color:#00d4ff">{ratio}</div>
                </div>
                """, unsafe_allow_html=True)

            # Row 2
            col4, col5, col6 = st.columns(3)

            with col4:
                st.markdown(f"""
                <div style="background:#111;border:1px solid #222;border-radius:4px;padding:20px;text-align:center">
                    <div style="font-size:11px;color:#888;text-transform:uppercase;letter-spacing:1px;margin-bottom:8px">Follow-back Rate</div>
                    <div style="font-size:24px;font-weight:700;color:{fbr_color}">{follow_back_rate:.1f}%</div>
                </div>
                """, unsafe_allow_html=True)

            with col5:
                st.markdown(f"""
                <div style="background:#111;border:1px solid #222;border-radius:4px;padding:20px;text-align:center">
                    <div style="font-size:11px;color:#888;text-transform:uppercase;letter-spacing:1px;margin-bottom:8px">Growth Rate</div>
                    <div style="font-size:24px;font-weight:700;color:#4ade80">{growth_rate:+.1f}/day</div>
                </div>
                """, unsafe_allow_html=True)

            with col6:
                st.markdown(f"""
                <div style="background:#111;border:1px solid #222;border-radius:4px;padding:20px;text-align:center">
                    <div style="font-size:11px;color:#888;text-transform:uppercase;letter-spacing:1px;margin-bottom:8px">Non-Followers</div>
                    <div style="font-size:24px;font-weight:700;color:#c8c8c8">{non_followers:,}</div>
                </div>
                """, unsafe_allow_html=True)

        except Exception as e:
            st.error(f"Failed to fetch stats: {str(e)[:200]}")
            history = load_history()
            chart_data = get_chart_data(history)

    # Dashboard is now just the ticker strip above


# =============================================================
# LIKE TAB
# =============================================================

if page == "LIKE":
    st.markdown("""
    <div style="margin-bottom:20px">
        <span style="font-size:11px;text-transform:uppercase;letter-spacing:2px;color:#888">Like Bot</span>
        <br>
        <span style="font-size:13px;color:#888">Like posts from non-followers to trigger notifications</span>
    </div>
    """, unsafe_allow_html=True)

    # Check if account is configured
    if not st.session_state.handle or not st.session_state.password:
        st.warning("No account configured. Go to SETTINGS tab to add your account first.")
    else:
        # Show account
        st.markdown(f"""
        <div style="margin-bottom:20px">
            <span style="display:inline-block;background:#1a1a1a;border:1px solid #333;padding:6px 14px;border-radius:2px;font-size:13px;font-family:JetBrains Mono,monospace">@{st.session_state.handle}</span>
        </div>
        """, unsafe_allow_html=True)

        # Config
        col1, col2, col3, col4, col5 = st.columns(5)

        with col1:
            batch_size = st.number_input("BATCH SIZE", min_value=10, max_value=500, value=200, step=10,
                help="Number of non-followers to like per run. Start with 50 to test.")
        with col2:
            likes_per_user = st.number_input("LIKES PER USER", min_value=1, max_value=5, value=2, step=1,
                help="How many posts to like per person. 2 is recommended.")
        with col3:
            daily_cap = st.number_input("DAILY CAP", min_value=10, max_value=1000, value=400, step=10, key="like_daily_cap",
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

        with col_btn:
            if runner.running:
                # Bot is running - show STOP button
                if st.button("⏹ STOP", key="stop_like", use_container_width=True, type="primary"):
                    runner.stop()
                    st.rerun()
            else:
                # Bot is stopped - show RUN button
                run_clicked = st.button("▶ RUN LIKE", key="run_like", use_container_width=True)

        with col_info:
            status_text = "RUNNING — click STOP to halt" if runner.running else f"@{st.session_state.handle} · batch={batch_size} · delay={delay_min}-{delay_max}s"
            st.markdown(f"""
            <div style="padding:10px 0;font-size:12px;color:#888">
                <strong style="color:#c8c8c8">{status_text}</strong>
            </div>
            """, unsafe_allow_html=True)

        # Live log
        st.markdown("""
        <div class="panel" style="margin-top:20px">
            <div class="panel-header">
                <span class="title">Live Output</span>
                <span class="status idle" id="log-status">IDLE</span>
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
                account = [{"handle": st.session_state.handle, "password": st.session_state.password, "enabled": True}]
                runner.start(
                    like_bot_run,
                    account,
                    batch_size,
                    likes_per_user,
                    delay_min,
                    delay_max,
                )
                st.rerun()

        # Bot is running - show logs and auto-refresh
        if runner.running:
            # Display current logs
            logs = runner.get_logs()
            if logs:
                log_text = "\n".join(logs[-50:])
                log_placeholder.code(log_text, language="bash")
            else:
                log_placeholder.code("Starting bot...", language="bash")

            # Auto-refresh every 2 seconds to show new logs
            time.sleep(2)
            st.rerun()

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
                runner.clear()
            elif results:
                total_liked = sum(r["liked"] for r in results)
                total_skipped = sum(r["skipped"] for r in results)
                total_errors = sum(r["errors"] for r in results)
                if runner.stop_requested:
                    st.warning(f"Like bot stopped: {total_liked} liked, {total_skipped} skipped, {total_errors} errors")
                else:
                    st.success(f"Like bot complete: {total_liked} liked, {total_skipped} skipped, {total_errors} errors")
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
        <span style="font-size:13px;color:#888">Copy followers from target accounts in your niche</span>
    </div>
    """, unsafe_allow_html=True)

    # Check if account is configured
    if not st.session_state.handle or not st.session_state.password:
        st.warning("No account configured. Go to SETTINGS tab to add your account first.")
    else:
        # Show account with target input
        st.markdown("""
        <div style="margin-bottom:10px">
            <span style="font-size:11px;text-transform:uppercase;letter-spacing:2px;color:#888">Assign Target Account</span>
        </div>
        """, unsafe_allow_html=True)

        col1, col2, col3 = st.columns([2, 1, 2])

        with col1:
            st.markdown(f"""
            <div style="padding:10px 0;font-size:14px;font-weight:600;color:#c8c8c8">
                @{st.session_state.handle}
            </div>
            """, unsafe_allow_html=True)

        with col2:
            st.markdown(f"""
            <div style="padding:10px 0;font-size:14px;color:#888;text-align:center">
                →
            </div>
            """, unsafe_allow_html=True)

        with col3:
            target = st.text_input(
                f"TARGET FOR @{st.session_state.handle}",
                value=st.session_state.target,
                placeholder="karpathy.bsky.social",
                key="follow_target",
                label_visibility="collapsed",
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
            pull_limit = st.number_input("PULL LIMIT", min_value=10, max_value=500, value=200, step=10,
                help="Max followers to pull from target account. 200 is a good start.")
        with col2:
            daily_cap = st.number_input("DAILY CAP", min_value=10, max_value=200, value=75, step=5,
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
        col_btn, col_info = st.columns([1, 3])

        with col_btn:
            if runner.running:
                # Bot is running - show STOP button
                if st.button("⏹ STOP", key="stop_follow", use_container_width=True, type="primary"):
                    runner.stop()
                    st.rerun()
            else:
                # Bot is stopped - show RUN button
                follow_run_clicked = st.button("▶ RUN FOLLOW", key="run_follow", use_container_width=True)

        with col_info:
            status_text = "RUNNING — click STOP to halt" if runner.running else f"target {'✓' if st.session_state.target.strip() else '✗'} · pull={pull_limit} · cap={daily_cap} · delay={follow_delay_min}-{follow_delay_max}s"
            st.markdown(f"""
            <div style="padding:10px 0;font-size:12px;color:#888">
                <strong style="color:#c8c8c8">{status_text}</strong>
            </div>
            """, unsafe_allow_html=True)

        # Live log
        st.markdown("""
        <div class="panel" style="margin-top:20px">
            <div class="panel-header">
                <span class="title">Live Output</span>
                <span class="status idle">IDLE</span>
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
                        "password": st.session_state.password,
                        "target": target,
                        "enabled": True
                    }]
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

        # Bot is running - show logs and auto-refresh
        if runner.running:
            # Display current logs
            logs = runner.get_logs()
            if logs:
                log_text = "\n".join(logs[-50:])
                follow_log_placeholder.code(log_text, language="bash")
            else:
                follow_log_placeholder.code("Starting bot...", language="bash")

            # Auto-refresh every 2 seconds to show new logs
            time.sleep(2)
            st.rerun()

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
                runner.clear()
            elif results:
                total_followed = sum(r["followed"] for r in results)
                total_liked = sum(r["liked"] for r in results)
                total_errors = sum(r["errors"] for r in results)
                if runner.stop_requested:
                    st.warning(f"Follow bot stopped: {total_followed} followed, {total_liked} liked, {total_errors} errors")
                else:
                    st.success(f"Follow bot complete: {total_followed} followed, {total_liked} liked, {total_errors} errors")
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
    if not st.session_state.handle or not st.session_state.password:
        st.warning("No account configured. Go to SETTINGS tab to add your account first.")
    else:
        # Show account
        st.markdown(f"""
        <div style="margin-bottom:20px">
            <span style="display:inline-block;background:#1a1a1a;border:1px solid #333;padding:6px 14px;border-radius:2px;font-size:13px;font-family:JetBrains Mono,monospace">@{st.session_state.handle}</span>
        </div>
        """, unsafe_allow_html=True)

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
            daily_cap = st.number_input("DAILY CAP", min_value=10, max_value=200, value=75, step=5,
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

        with col_info:
            status_text = "RUNNING — click STOP to halt" if runner.running else f"threshold={days_threshold}d · cap={daily_cap} · delay={unfollow_delay_min}-{unfollow_delay_max}s · {len(exemptions)} exemptions"
            st.markdown(f"""
            <div style="padding:10px 0;font-size:12px;color:#888">
                <strong style="color:#c8c8c8">{status_text}</strong>
            </div>
            """, unsafe_allow_html=True)

        # Preview results
        if preview_clicked:
            st.markdown("""
            <div style="margin-top:20px;margin-bottom:10px">
                <span style="font-size:11px;text-transform:uppercase;letter-spacing:2px;color:#888">Preview</span>
            </div>
            """, unsafe_allow_html=True)

            # Create single account list for preview
            account = [{"handle": st.session_state.handle, "password": st.session_state.password, "enabled": True}]

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
        st.markdown("""
        <div class="panel" style="margin-top:20px">
            <div class="panel-header">
                <span class="title">Live Output</span>
                <span class="status idle">IDLE</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        unfollow_log_placeholder = st.empty()

        # Run the bot (when RUN button clicked)
        if not runner.running and unfollow_clicked:
            # Check if another bot is running
            if any_bot_running():
                running_bot = get_running_bot_name()
                st.error(f"Cannot start Unfollow Bot — {running_bot} Bot is already running. Stop it first or wait for it to finish.")
            # Validate delays
            elif unfollow_delay_min > unfollow_delay_max:
                st.error("Min delay must be <= max delay")
            else:
                # Start bot in background thread
                account = [{"handle": st.session_state.handle, "password": st.session_state.password, "enabled": True}]
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

        # Bot is running - show logs and auto-refresh
        if runner.running:
            # Display current logs
            logs = runner.get_logs()
            if logs:
                log_text = "\n".join(logs[-50:])
                unfollow_log_placeholder.code(log_text, language="bash")
            else:
                unfollow_log_placeholder.code("Starting bot...", language="bash")

            # Auto-refresh every 2 seconds to show new logs
            time.sleep(2)
            st.rerun()

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
                runner.clear()
            elif results:
                total_unfollowed = sum(r["unfollowed"] for r in results)
                total_skipped = sum(r["skipped"] for r in results)
                total_errors = sum(r["errors"] for r in results)
                if runner.stop_requested:
                    st.warning(f"Unfollow bot stopped: {total_unfollowed} unfollowed, {total_skipped} skipped, {total_errors} errors")
                else:
                    st.success(f"Unfollow bot complete: {total_unfollowed} unfollowed, {total_skipped} skipped, {total_errors} errors")
                runner.clear()

            # Show existing log
            logs = runner.get_logs()
            if logs:
                log_text = "\n".join(logs[-50:])
                unfollow_log_placeholder.code(log_text, language="bash")
            else:
                unfollow_log_placeholder.code("Waiting to start...", language="bash")


# =============================================================
# SETTINGS TAB
# =============================================================

if page == "SETTINGS":
    st.markdown("""
    <div style="margin-bottom:20px">
        <span style="font-size:11px;text-transform:uppercase;letter-spacing:2px;color:#888">Account Configuration</span>
        <br>
        <span style="font-size:13px;color:#888">Add your Bluesky account. App password is stored in session only.</span>
    </div>
    """, unsafe_allow_html=True)

    # Account input
    col1, col2 = st.columns(2)

    with col1:
        handle = st.text_input(
            "HANDLE",
            value=st.session_state.handle,
            placeholder="alice.bsky.social",
            key="settings_handle",
        )
        st.session_state.handle = handle

    with col2:
        password = st.text_input(
            "APP PASSWORD",
            value=st.session_state.password,
            type="password",
            placeholder="xxxx-xxxx-xxxx-xxxx",
            key="settings_password",
        )
        st.session_state.password = password

    # Save button with auth verification
    if st.button("SAVE & VERIFY", key="save_accounts"):
        handle = st.session_state.handle.strip()
        password = st.session_state.password.strip()

        if not handle or not password:
            st.error("Please enter both handle and app password.")
        else:
            try:
                from utils.auth import login
                client = login(handle, password)
                profile = client.app.bsky.actor.get_profile({"actor": handle})
                st.session_state.verified = True
                st.success(f"Authenticated as @{profile.handle} · {profile.followers_count or 0:,} followers")
                st.rerun()
            except Exception as e:
                st.session_state.verified = False
                st.error(f"Authentication failed: {e}")

    # Verification status - shows AFTER button handler
    if st.session_state.verified:
        st.markdown("✅ Account verified")
    else:
        st.markdown("— Not verified")

    # Instructions
    st.markdown("""
    <div class="panel" style="margin-top:20px">
        <div class="panel-header">
            <span class="title">How to get app passwords</span>
        </div>
        <div class="panel-body" style="font-size:12px;color:#888;line-height:1.8">
            1. Go to bsky.app → Settings → App Passwords<br>
            2. Click "Generate"<br>
            3. Copy the password (looks like <code>abcd-efgh-ijkl-mnop</code>)<br>
            4. Paste it above<br>
            <br>
            <span style="color:#888">Passwords are stored in your browser session only. They are never saved to disk or sent anywhere except Bluesky's API.</span>
        </div>
    </div>
    """, unsafe_allow_html=True)
