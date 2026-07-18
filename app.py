"""
Bluesky Growth — Terminal Style Dashboard
Streamlit app for managing Bluesky follow/like/unfollow bots.
"""

import streamlit as st
import time
from datetime import datetime

from utils.auth import login
from utils.stats import get_stats
from utils.tracker import load_history, save_snapshot, get_chart_data
from bots.like_bot import like_bot_run
from bots.follow_bot import follow_bot_run
from bots.unfollow_bot import unfollow_bot_run, get_unfollow_preview

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
.stTabs [data-baseweb="tab-list"] {
    gap: 0;
    background: #111;
    border: 1px solid #222;
    border-radius: 2px;
}
.stTabs [data-baseweb="tab"] {
    color: #888;
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
        {"handle": "", "password": "", "target": "", "enabled": True},
        {"handle": "", "password": "", "target": "", "enabled": True},
        {"handle": "", "password": "", "target": "", "enabled": True},
        {"handle": "", "password": "", "target": "", "enabled": True},
        {"handle": "", "password": "", "target": "", "enabled": True},
    ]

if "bot_running" not in st.session_state:
    st.session_state.bot_running = False

# Per-bot running states
if "like_bot_running" not in st.session_state:
    st.session_state.like_bot_running = False

if "follow_bot_running" not in st.session_state:
    st.session_state.follow_bot_running = False

if "unfollow_bot_running" not in st.session_state:
    st.session_state.unfollow_bot_running = False

# Separate log lines for each bot
if "like_log_lines" not in st.session_state:
    st.session_state.like_log_lines = []

if "follow_log_lines" not in st.session_state:
    st.session_state.follow_log_lines = []

if "unfollow_log_lines" not in st.session_state:
    st.session_state.unfollow_log_lines = []


# =============================================================
# HEADER
# =============================================================

st.markdown("""
<div class="topbar">
    <div class="brand">bsky_growth <span>v1.0</span></div>
    <div style="color:#888;font-size:11px;font-family:'JetBrains Mono',monospace;text-transform:uppercase;letter-spacing:2px">
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
    # Get configured accounts
    valid_accounts = [
        a for a in st.session_state.accounts
        if a.get("enabled") and a.get("handle") and a.get("password")
    ]

    if not valid_accounts:
        st.info("Configure your accounts in the SETTINGS tab to see live stats here.")
    else:
        # Account selector dropdown
        account_options = [f"@{a['handle']}" for a in valid_accounts]
        selected = st.selectbox("SELECT ACCOUNT", account_options, key="dashboard_account")

        # Get selected account
        selected_idx = account_options.index(selected)
        selected_account = valid_accounts[selected_idx]

        # Fetch stats for selected account
        try:
            from utils.auth import login
            from utils.stats import get_stats
            client = login(selected_account["handle"], selected_account["password"])
            stats = get_stats(selected_account["handle"], client)

            followers = stats["followers"]
            following = stats["following"]
            ratio = stats["ratio"]

            # Save snapshot
            save_snapshot(followers, following)

            # Ticker strip
            st.markdown(f"""
            <div class="ticker">
                <div class="ticker-item">
                    <span class="label">Followers</span>
                    <span class="value">{followers:,}</span>
                </div>
                <div class="ticker-item">
                    <span class="label">Following</span>
                    <span class="value">{following:,}</span>
                </div>
                <div class="ticker-item">
                    <span class="label">Ratio</span>
                    <span class="value">{ratio}</span>
                </div>
                <div class="ticker-item">
                    <span class="label">Handle</span>
                    <span class="value">@{selected_account['handle']}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

        except Exception as e:
            st.error(f"Failed to fetch stats for @{selected_account['handle']}: {str(e)[:200]}")

    # Load history for chart
    history = load_history()
    chart_data = get_chart_data(history)

    # Growth chart
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("""
        <div style="margin-top:20px;margin-bottom:10px">
            <span style="font-size:11px;text-transform:uppercase;letter-spacing:2px;color:#888">Follower Growth</span>
        </div>
        """, unsafe_allow_html=True)

        if len(chart_data) >= 2:
            # Show line chart with Streamlit
            import pandas as pd
            df = pd.DataFrame(chart_data)
            df["date"] = pd.to_datetime(df["date"])
            df = df.set_index("date")

            st.line_chart(df[["followers"]], use_container_width=True)

            # Show stats
            first = chart_data[0]
            last = chart_data[-1]
            change = last["followers"] - first["followers"]
            days = len(chart_data)

            st.markdown(f"""
            <div style="font-size:12px;color:#888;margin-top:8px">
                {days} days tracked · {change:+,} followers · since {first['date']}
            </div>
            """, unsafe_allow_html=True)
        elif len(chart_data) == 1:
            st.markdown(f"""
            <div style="padding:20px;text-align:center;color:#888;font-size:12px">
                First snapshot saved today ({chart_data[0]['date']}).<br>
                Come back tomorrow to see the growth chart.
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div style="padding:20px;text-align:center;color:#666;font-size:12px">
                No data yet. Configure accounts to start tracking.
            </div>
            """, unsafe_allow_html=True)

    with col2:
        # Determine bot statuses
        like_status = "active" if st.session_state.like_bot_running else "idle"
        follow_status = "active" if st.session_state.follow_bot_running else "idle"
        unfollow_status = "active" if st.session_state.unfollow_bot_running else "idle"

        like_label = "RUNNING" if like_status == "active" else "IDLE"
        follow_label = "RUNNING" if follow_status == "active" else "IDLE"
        unfollow_label = "RUNNING" if unfollow_status == "active" else "IDLE"

        # Count log lines for progress
        like_progress = f"{len(st.session_state.like_log_lines)} lines" if st.session_state.like_log_lines else "—"
        follow_progress = f"{len(st.session_state.follow_log_lines)} lines" if st.session_state.follow_log_lines else "—"
        unfollow_progress = f"{len(st.session_state.unfollow_log_lines)} lines" if st.session_state.unfollow_log_lines else "—"

        st.markdown(f"""
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
                            <td><span class="tag {like_status}">{like_label}</span></td>
                            <td>{like_progress}</td>
                        </tr>
                        <tr>
                            <td>FOLLOW BOT</td>
                            <td><span class="tag {follow_status}">{follow_label}</span></td>
                            <td>{follow_progress}</td>
                        </tr>
                        <tr>
                            <td>UNFOLLOW BOT</td>
                            <td><span class="tag {unfollow_status}">{unfollow_label}</span></td>
                            <td>{unfollow_progress}</td>
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
        <span style="font-size:11px;text-transform:uppercase;letter-spacing:2px;color:#888">Like Bot</span>
        <br>
        <span style="font-size:13px;color:#888">Like posts from non-followers to trigger notifications</span>
    </div>
    """, unsafe_allow_html=True)

    # Show connected accounts
    configured_accounts = [
        a for a in st.session_state.accounts
        if a.get("handle") and a.get("password")
    ]

    if not configured_accounts:
        st.warning("No accounts configured. Go to SETTINGS tab to add accounts first.")
    else:
        st.markdown("""
        <div style="margin-bottom:10px">
            <span style="font-size:11px;text-transform:uppercase;letter-spacing:2px;color:#888">Connected Accounts</span>
        </div>
        """, unsafe_allow_html=True)

        # Show accounts as pills/chips
        accounts_html = " ".join([
            f'<span style="display:inline-block;background:#1a1a1a;border:1px solid #333;padding:6px 14px;border-radius:20px;font-size:13px;margin:0 6px 6px 0;font-family:JetBrains Mono,monospace">@{a["handle"]}</span>'
            for a in configured_accounts
        ])
        st.markdown(f"""
        <div style="margin-bottom:20px">
            {accounts_html}
        </div>
        """, unsafe_allow_html=True)

        # Config
        col1, col2, col3, col4, col5 = st.columns(5)

        with col1:
            batch_size = st.number_input("BATCH SIZE", min_value=10, max_value=500, value=200, step=10)
        with col2:
            likes_per_user = st.number_input("LIKES PER USER", min_value=1, max_value=5, value=2, step=1)
        with col3:
            daily_cap = st.number_input("DAILY CAP", min_value=10, max_value=1000, value=400, step=10, key="like_daily_cap")
        with col4:
            delay_min = st.number_input("MIN DELAY (sec)", min_value=1, max_value=60, value=5, step=1)
        with col5:
            delay_max = st.number_input("MAX DELAY (sec)", min_value=1, max_value=60, value=10, step=1)

        # Run button
        col_btn, col_info = st.columns([1, 3])

        with col_btn:
            run_clicked = st.button("▶ RUN LIKE BOT", key="run_like", use_container_width=True)

        with col_info:
            st.markdown(f"""
            <div style="padding:10px 0;font-size:12px;color:#888">
                <strong style="color:#c8c8c8">{len(configured_accounts)} accounts</strong> connected ·
                batch={batch_size} · daily cap={daily_cap} · delay={delay_min}-{delay_max}s ·
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
            # Validate delays
            if delay_min > delay_max:
                st.error("Min delay must be <= max delay")
            else:
                st.session_state.like_bot_running = True
                st.session_state.like_log_lines = []

                # Callback to update log display in real-time
                def log_callback(line):
                    st.session_state.like_log_lines.append(line)
                    log_text = "\n".join(st.session_state.like_log_lines[-50:])
                    log_placeholder.code(log_text, language="bash")

                # Run the bot with spinner
                with st.spinner("Running Like Bot..."):
                    try:
                        like_bot_run(
                            configured_accounts,
                            batch_size,
                            likes_per_user,
                            delay_min,
                            delay_max,
                            log_callback=log_callback,
                        )
                        st.success("Like bot run complete!")
                    except Exception as e:
                        st.error(f"Bot error: {e}")

                st.session_state.like_bot_running = False
        else:
            # Show existing log or placeholder
            if st.session_state.like_log_lines:
                log_text = "\n".join(st.session_state.like_log_lines[-50:])
                log_placeholder.code(log_text, language="bash")
            else:
                log_placeholder.code("Waiting to start...", language="bash")


# =============================================================
# FOLLOW BOT TAB (Placeholder)
# =============================================================

with tab_follow:
    st.markdown("""
    <div style="margin-bottom:20px">
        <span style="font-size:11px;text-transform:uppercase;letter-spacing:2px;color:#888">Follow Bot</span>
        <br>
        <span style="font-size:13px;color:#888">Copy followers from target accounts in your niche</span>
    </div>
    """, unsafe_allow_html=True)

    # Get configured accounts from Settings
    configured_accounts = [
        a for a in st.session_state.accounts
        if a.get("handle") and a.get("password")
    ]

    if not configured_accounts:
        st.warning("No accounts configured. Go to SETTINGS tab to add accounts first.")
    else:
        # Show accounts with target input
        st.markdown("""
        <div style="margin-bottom:10px">
            <span style="font-size:11px;text-transform:uppercase;letter-spacing:2px;color:#888">Assign Target Accounts</span>
        </div>
        """, unsafe_allow_html=True)

        for i, acc in enumerate(configured_accounts):
            col1, col2, col3 = st.columns([2, 1, 2])

            with col1:
                st.markdown(f"""
                <div style="padding:10px 0;font-size:14px;font-weight:600;color:#c8c8c8">
                    @{acc['handle']}
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
                    f"TARGET FOR @{acc['handle']}",
                    value=acc.get("target", ""),
                    placeholder="karpathy.bsky.social",
                    key=f"follow_target_{i}",
                    label_visibility="collapsed",
                )
                st.session_state.accounts[i]["target"] = target

        # Config
        st.markdown("""
        <div style="margin-top:20px;margin-bottom:10px">
            <span style="font-size:11px;text-transform:uppercase;letter-spacing:2px;color:#888">Bot Settings</span>
        </div>
        """, unsafe_allow_html=True)

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            pull_limit = st.number_input("PULL LIMIT", min_value=10, max_value=500, value=200, step=10)
        with col2:
            daily_cap = st.number_input("DAILY CAP", min_value=10, max_value=200, value=75, step=5)
        with col3:
            follow_delay_min = st.number_input("MIN DELAY (sec)", min_value=1, max_value=60, value=5, step=1, key="follow_delay_min")
        with col4:
            follow_delay_max = st.number_input("MAX DELAY (sec)", min_value=1, max_value=60, value=15, step=1, key="follow_delay_max")

        auto_like = st.checkbox("Auto-like posts after following", value=True)

        # Run button
        col_btn, col_info = st.columns([1, 3])

        with col_btn:
            follow_run_clicked = st.button("▶ RUN FOLLOW BOT", key="run_follow", use_container_width=True)

        with col_info:
            valid_count = sum(1 for a in configured_accounts if a.get("target"))
            st.markdown(f"""
            <div style="padding:10px 0;font-size:12px;color:#888">
                <strong style="color:#c8c8c8">{valid_count} accounts</strong> with targets ·
                pull={pull_limit} · cap={daily_cap} · delay={follow_delay_min}-{follow_delay_max}s
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

        # Run the bot
        if follow_run_clicked:
            # Validate delays
            if follow_delay_min > follow_delay_max:
                st.error("Min delay must be <= max delay")
            else:
                # Validate accounts with targets
                valid_accounts = [
                    a for a in configured_accounts
                    if a.get("target")
                ]

                if not valid_accounts:
                    st.error("No targets configured. Add a target account for at least one of your accounts.")
                else:
                    st.session_state.follow_bot_running = True
                    st.session_state.follow_log_lines = []

                    # Callback to update log display
                    def follow_log_callback(line):
                        st.session_state.follow_log_lines.append(line)
                        log_text = "\n".join(st.session_state.follow_log_lines[-50:])
                        follow_log_placeholder.code(log_text, language="bash")

                    # Run the bot with spinner
                    with st.spinner("Running Follow Bot..."):
                        try:
                            follow_bot_run(
                                valid_accounts,
                                pull_limit,
                                daily_cap,
                                follow_delay_min,
                                follow_delay_max,
                                auto_like,
                                log_callback=follow_log_callback,
                            )
                            st.success("Follow bot run complete!")
                        except Exception as e:
                            st.error(f"Bot error: {e}")

                    st.session_state.follow_bot_running = False
        else:
            # Show existing log or placeholder
            if st.session_state.follow_log_lines:
                log_text = "\n".join(st.session_state.follow_log_lines[-50:])
                follow_log_placeholder.code(log_text, language="bash")
            else:
                follow_log_placeholder.code("Waiting to start...", language="bash")


# =============================================================
# UNFOLLOW BOT TAB (Placeholder)
# =============================================================

with tab_unfollow:
    st.markdown("""
    <div style="margin-bottom:20px">
        <span style="font-size:11px;text-transform:uppercase;letter-spacing:2px;color:#888">Unfollow Bot</span>
        <br>
        <span style="font-size:13px;color:#888">Unfollow non-followers older than X days</span>
    </div>
    """, unsafe_allow_html=True)

    # Get configured accounts
    configured_accounts = [
        a for a in st.session_state.accounts
        if a.get("handle") and a.get("password")
    ]

    if not configured_accounts:
        st.warning("No accounts configured. Go to SETTINGS tab to add accounts first.")
    else:
        # Show connected accounts
        st.markdown("""
        <div style="margin-bottom:10px">
            <span style="font-size:11px;text-transform:uppercase;letter-spacing:2px;color:#888">Connected Accounts</span>
        </div>
        """, unsafe_allow_html=True)

        accounts_html = " ".join([
            f'<span style="display:inline-block;background:#1a1a1a;border:1px solid #333;padding:6px 14px;border-radius:20px;font-size:13px;margin:0 6px 6px 0;font-family:JetBrains Mono,monospace">@{a["handle"]}</span>'
            for a in configured_accounts
        ])
        st.markdown(f"""
        <div style="margin-bottom:20px">
            {accounts_html}
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
                help="Only unfollow if followed more than X days ago")
        with col2:
            daily_cap = st.number_input("DAILY CAP", min_value=10, max_value=200, value=75, step=5,
                key="unfollow_daily_cap")
        with col3:
            unfollow_delay_min = st.number_input("MIN DELAY (sec)", min_value=1, max_value=60, value=5, step=1,
                key="unfollow_delay_min")
        with col4:
            unfollow_delay_max = st.number_input("MAX DELAY (sec)", min_value=1, max_value=60, value=15, step=1,
                key="unfollow_delay_max")

        # Exemptions
        st.markdown("""
        <div style="margin-top:20px;margin-bottom:10px">
            <span style="font-size:11px;text-transform:uppercase;letter-spacing:2px;color:#888">Exemptions</span>
            <span style="font-size:12px;color:#888;margin-left:10px">Accounts to never unfollow (one per line)</span>
        </div>
        """, unsafe_allow_html=True)

        exemptions_text = st.text_area(
            "EXEMPTIONS",
            value="karpathy.bsky.social\nbsky.app",
            height=100,
            key="unfollow_exemptions",
            label_visibility="collapsed",
        )
        exemptions = [e.strip() for e in exemptions_text.split("\n") if e.strip()]

        # Preview button
        col_preview, col_run, col_info = st.columns([1, 1, 2])

        with col_preview:
            preview_clicked = st.button("👁 PREVIEW", key="preview_unfollow", use_container_width=True)

        with col_run:
            unfollow_clicked = st.button("🚪 RUN UNFOLLOW BOT", key="run_unfollow", use_container_width=True)

        with col_info:
            st.markdown(f"""
            <div style="padding:10px 0;font-size:12px;color:#888">
                threshold={days_threshold}d · cap={daily_cap} · delay={unfollow_delay_min}-{unfollow_delay_max}s · {len(exemptions)} exemptions
            </div>
            """, unsafe_allow_html=True)

        # Preview results
        if preview_clicked:
            st.markdown("""
            <div style="margin-top:20px;margin-bottom:10px">
                <span style="font-size:11px;text-transform:uppercase;letter-spacing:2px;color:#888">Preview</span>
            </div>
            """, unsafe_allow_html=True)

            with st.spinner("Fetching preview data..."):
                preview_results = get_unfollow_preview(configured_accounts, days_threshold, exemptions)

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

        # Run the bot
        if unfollow_clicked:
            # Validate delays
            if unfollow_delay_min > unfollow_delay_max:
                st.error("Min delay must be <= max delay")
            else:
                st.session_state.unfollow_bot_running = True
                st.session_state.unfollow_log_lines = []

                # Callback to update log display
                def unfollow_log_callback(line):
                    st.session_state.unfollow_log_lines.append(line)
                    log_text = "\n".join(st.session_state.unfollow_log_lines[-50:])
                    unfollow_log_placeholder.code(log_text, language="bash")

                # Run the bot with spinner
                with st.spinner("Running Unfollow Bot..."):
                    try:
                        unfollow_bot_run(
                            configured_accounts,
                            days_threshold,
                            daily_cap,
                            unfollow_delay_min,
                            unfollow_delay_max,
                            exemptions,
                            log_callback=unfollow_log_callback,
                        )
                        st.success("Unfollow bot run complete!")
                    except Exception as e:
                        st.error(f"Bot error: {e}")

                st.session_state.unfollow_bot_running = False
        else:
            # Show existing log or placeholder
            if st.session_state.unfollow_log_lines:
                log_text = "\n".join(st.session_state.unfollow_log_lines[-50:])
                unfollow_log_placeholder.code(log_text, language="bash")
            else:
                unfollow_log_placeholder.code("Waiting to start...", language="bash")


# =============================================================
# SETTINGS TAB
# =============================================================

with tab_settings:
    st.markdown("""
    <div style="margin-bottom:20px">
        <span style="font-size:11px;text-transform:uppercase;letter-spacing:2px;color:#888">Account Configuration</span>
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

    # Save button with auth verification
    if st.button("SAVE & VERIFY ACCOUNTS", key="save_accounts"):
        st.session_state.log_lines = []  # Clear any previous logs

        results = []
        for i, acc in enumerate(st.session_state.accounts):
            handle = acc.get("handle", "").strip()
            password = acc.get("password", "").strip()

            if not handle or not password:
                results.append({"index": i+1, "handle": handle or "empty", "status": "skip", "msg": "No credentials"})
                continue

            try:
                from utils.auth import login
                client = login(handle, password)
                profile = client.app.bsky.actor.get_profile({"actor": handle})
                results.append({
                    "index": i+1,
                    "handle": handle,
                    "status": "ok",
                    "msg": f"Authenticated as @{profile.handle} · {profile.followers_count or 0:,} followers"
                })
            except Exception as e:
                results.append({
                    "index": i+1,
                    "handle": handle,
                    "status": "error",
                    "msg": str(e)[:80]
                })

        # Display results
        for r in results:
            if r["status"] == "ok":
                st.success(f"Account {r['index']} @{r['handle']}: {r['msg']}")
            elif r["status"] == "error":
                st.error(f"Account {r['index']} @{r['handle']}: {r['msg']}")
            else:
                st.info(f"Account {r['index']}: {r['msg']}")

        # Count successes
        ok_count = sum(1 for r in results if r["status"] == "ok")
        if ok_count > 0:
            st.success(f"{ok_count} account(s) verified and ready to use.")
        else:
            st.warning("No accounts verified. Check your handles and app passwords.")

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
