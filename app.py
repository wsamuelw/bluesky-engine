"""
Bluesky Growth — Terminal Style Dashboard
Streamlit app for managing Bluesky follow/like/unfollow bots.
"""

import streamlit as st
import asyncio
import time
from datetime import datetime

from utils.auth import login
from utils.stats import get_stats
from bots.like_bot import run_all as run_like_bot

# =============================================================
# PAGE CONFIG
# =============================================================

st.set_page_config(
    page_title="BSKY_GROWTH",
    page_icon="🦋",
    layout="wide",
    initial_sidebar_state="collapsed",
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
.topbar {
    background: #111;
    border-bottom: 1px solid #222;
    padding: 12px 20px;
    margin: -2rem -2rem 2rem -2rem;
    display: flex;
    align-items: center;
    justify-content: space-between;
}
.topbar .brand {
    color: #00d4ff;
    font-size: 16px;
    font-weight: 700;
    font-family: 'JetBrains Mono', monospace;
}
.topbar .brand span { color: #555; }

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
    color: #555;
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
    color: #555;
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
.log-output .time { color: #333; }
.log-output .ok { color: #00d4ff; }
.log-output .info { color: #555; }
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
    color: #555;
    font-size: 12px;
    font-family: 'JetBrains Mono', monospace;
}
.action-bar .info strong { color: #c8c8c8; }

/* Buttons */
.stButton > button {
    background: #00d4ff;
    color: #0a0a0a;
    border: none;
    padding: 10px 24px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 12px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 1px;
    border-radius: 2px;
}
.stButton > button:hover {
    background: #00b8db;
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
.tag.idle { background: #333; color: #666; }

/* Hide Streamlit elements */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}
.stDeployButton {display: none;}

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
    gap: 0;
    background: #111;
    border: 1px solid #222;
    border-radius: 2px;
}
.stTabs [data-baseweb="tab"] {
    color: #555;
    font-family: 'JetBrains Mono', monospace;
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 1px;
    padding: 10px 20px;
}
.stTabs [aria-selected="true"] {
    color: #00d4ff;
    background: #1a1a1a;
}
.stTabs [data-baseweb="tab-border"] {
    display: none;
}
.stTabs [data-baseweb="tab-highlight"] {
    background: #00d4ff;
}
</style>
""", unsafe_allow_html=True)


# =============================================================
# SESSION STATE
# =============================================================

if "accounts" not in st.session_state:
    st.session_state.accounts = [
        {"handle": "", "password": "", "enabled": True},
        {"handle": "", "password": "", "enabled": True},
        {"handle": "", "password": "", "enabled": True},
        {"handle": "", "password": "", "enabled": True},
        {"handle": "", "password": "", "enabled": True},
    ]

if "bot_running" not in st.session_state:
    st.session_state.bot_running = False

if "log_lines" not in st.session_state:
    st.session_state.log_lines = []


# =============================================================
# HEADER
# =============================================================

st.markdown("""
<div class="topbar">
    <div class="brand">bsky_growth <span>v1.0</span></div>
    <div style="color:#555;font-size:11px;font-family:'JetBrains Mono',monospace;text-transform:uppercase;letter-spacing:2px">
        Bluesky Follower Growth Platform
    </div>
</div>
""", unsafe_allow_html=True)


# =============================================================
# TABS
# =============================================================

tab_dashboard, tab_like, tab_follow, tab_unfollow, tab_settings = st.tabs([
    "DASHBOARD", "LIKE BOT", "FOLLOW BOT", "UNFOLLOW BOT", "SETTINGS"
])


# =============================================================
# DASHBOARD TAB
# =============================================================

with tab_dashboard:
    # Ticker strip — placeholder stats
    st.markdown("""
    <div class="ticker">
        <div class="ticker-item">
            <span class="label">Followers</span>
            <span class="value">—</span>
        </div>
        <div class="ticker-item">
            <span class="label">Following</span>
            <span class="value">—</span>
        </div>
        <div class="ticker-item">
            <span class="label">Ratio</span>
            <span class="value">—</span>
        </div>
        <div class="ticker-item">
            <span class="label">Likes Today</span>
            <span class="value">0</span>
        </div>
        <div class="ticker-item">
            <span class="label">Uptime</span>
            <span class="value">0m</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.info("Configure your accounts in the SETTINGS tab to see live stats here.")

    # Growth chart placeholder
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("""
        <div class="panel">
            <div class="panel-header">
                <span class="title">Follower Growth — 30d</span>
                <span class="status idle">NO DATA</span>
            </div>
            <div class="panel-body">
                <div style="height:140px;display:flex;align-items:center;justify-content:center;color:#333;font-size:12px">
                    Configure accounts to see growth chart
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown("""
        <div class="panel">
            <div class="panel-header">
                <span class="title">Bot Status</span>
            </div>
            <div class="panel-body">
                <table class="data-table">
                    <thead>
                        <tr><th>Bot</th><th>Status</th><th>Progress</th></tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td>LIKE BOT</td>
                            <td><span class="tag idle">IDLE</span></td>
                            <td>—</td>
                        </tr>
                        <tr>
                            <td>FOLLOW BOT</td>
                            <td><span class="tag idle">IDLE</span></td>
                            <td>—</td>
                        </tr>
                        <tr>
                            <td>UNFOLLOW BOT</td>
                            <td><span class="tag idle">IDLE</span></td>
                            <td>—</td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>
        """, unsafe_allow_html=True)


# =============================================================
# LIKE BOT TAB
# =============================================================

with tab_like:
    st.markdown("""
    <div style="margin-bottom:20px">
        <span style="font-size:11px;text-transform:uppercase;letter-spacing:2px;color:#555">Like Bot</span>
        <br>
        <span style="font-size:13px;color:#888">Like posts from non-followers to trigger notifications</span>
    </div>
    """, unsafe_allow_html=True)

    # Config
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        batch_size = st.number_input("BATCH SIZE", min_value=10, max_value=1000, value=200, step=10)
    with col2:
        likes_per_user = st.number_input("LIKES PER USER", min_value=1, max_value=5, value=2, step=1)
    with col3:
        delay_min = st.number_input("MIN DELAY (sec)", min_value=1, max_value=60, value=5, step=1)
    with col4:
        delay_max = st.number_input("MAX DELAY (sec)", min_value=1, max_value=60, value=10, step=1)

    # Run button
    col_btn, col_info = st.columns([1, 3])

    with col_btn:
        run_clicked = st.button("▶ RUN LIKE BOT", key="run_like", use_container_width=True)

    with col_info:
        enabled_count = sum(1 for a in st.session_state.accounts if a.get("enabled") and a.get("handle"))
        st.markdown(f"""
        <div style="padding:10px 0;font-size:12px;color:#555">
            <strong style="color:#c8c8c8">{enabled_count} accounts</strong> configured ·
            batch={batch_size} · delay={delay_min}-{delay_max}s ·
            est. {int(batch_size * (delay_min + delay_max) / 2 / 60)} min
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

    # Run the bot
    if run_clicked:
        # Validate accounts
        valid_accounts = [
            a for a in st.session_state.accounts
            if a.get("enabled") and a.get("handle") and a.get("password")
        ]

        if not valid_accounts:
            st.error("No valid accounts configured. Go to SETTINGS tab to add accounts.")
        else:
            st.session_state.bot_running = True
            st.session_state.log_lines = []

            # Update status to live
            st.markdown("""
            <script>
            document.getElementById('log-status').textContent = 'RUNNING';
            document.getElementById('log-status').className = 'status live';
            </script>
            """, unsafe_allow_html=True)

            # Run the bot and stream logs
            async def run_and_stream():
                async for line in run_like_bot(
                    valid_accounts,
                    batch_size,
                    likes_per_user,
                    delay_min,
                    delay_max,
                ):
                    st.session_state.log_lines.append(line)
                    # Update log display
                    log_text = "\n".join(st.session_state.log_lines[-50:])  # Last 50 lines
                    log_placeholder.code(log_text, language="bash")

            asyncio.run(run_and_stream())
            st.session_state.bot_running = False
            st.success("Like bot run complete!")
    else:
        # Show existing log or placeholder
        if st.session_state.log_lines:
            log_text = "\n".join(st.session_state.log_lines[-50:])
            log_placeholder.code(log_text, language="bash")
        else:
            log_placeholder.code("Waiting to start...", language="bash")


# =============================================================
# FOLLOW BOT TAB (Placeholder)
# =============================================================

with tab_follow:
    st.markdown("""
    <div class="panel">
        <div class="panel-header">
            <span class="title">Follow Bot</span>
            <span class="status idle">COMING SOON</span>
        </div>
        <div class="panel-body">
            <div style="text-align:center;padding:40px;color:#333;font-size:13px">
                Follow bot will be available in Phase 2.<br>
                Use the Colab notebook for now: <code>bluesky_bot.md</code>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)


# =============================================================
# UNFOLLOW BOT TAB (Placeholder)
# =============================================================

with tab_unfollow:
    st.markdown("""
    <div class="panel">
        <div class="panel-header">
            <span class="title">Unfollow Bot</span>
            <span class="status idle">COMING SOON</span>
        </div>
        <div class="panel-body">
            <div style="text-align:center;padding:40px;color:#333;font-size:13px">
                Unfollow bot will be available in Phase 2.<br>
                Currently in design — check mockup <code>4-unfollowbot-cards.html</code>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)


# =============================================================
# SETTINGS TAB
# =============================================================

with tab_settings:
    st.markdown("""
    <div style="margin-bottom:20px">
        <span style="font-size:11px;text-transform:uppercase;letter-spacing:2px;color:#555">Account Configuration</span>
        <br>
        <span style="font-size:13px;color:#888">Add your Bluesky accounts. App passwords are stored in session only.</span>
    </div>
    """, unsafe_allow_html=True)

    # Account inputs
    for i in range(5):
        col1, col2, col3 = st.columns([3, 3, 1])

        with col1:
            handle = st.text_input(
                f"HANDLE {i+1}",
                value=st.session_state.accounts[i].get("handle", ""),
                placeholder="alice.bsky.social",
                key=f"handle_{i}",
            )
            st.session_state.accounts[i]["handle"] = handle

        with col2:
            password = st.text_input(
                f"APP PASSWORD {i+1}",
                value=st.session_state.accounts[i].get("password", ""),
                type="password",
                placeholder="xxxx-xxxx-xxxx-xxxx",
                key=f"password_{i}",
            )
            st.session_state.accounts[i]["password"] = password

        with col3:
            enabled = st.checkbox(
                "ON",
                value=st.session_state.accounts[i].get("enabled", True),
                key=f"enabled_{i}",
            )
            st.session_state.accounts[i]["enabled"] = enabled

    # Save button
    if st.button("SAVE ACCOUNTS", key="save_accounts"):
        st.success("Accounts saved to session.")

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
            <span style="color:#555">Passwords are stored in your browser session only. They are never saved to disk or sent anywhere except Bluesky's API.</span>
        </div>
    </div>
    """, unsafe_allow_html=True)
