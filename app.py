"""
Bluesky Growth Engine — Terminal Style Dashboard
Streamlit app for managing Bluesky follow/like/unfollow bots.
"""

import streamlit as st
import subprocess
from pathlib import Path

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
# LOAD CSS
# =============================================================

css_path = Path(__file__).parent / "styles.css"
st.markdown(f"<style>{css_path.read_text()}</style>", unsafe_allow_html=True)

# =============================================================
# CACHED RESOURCES
# =============================================================

@st.cache_resource
def get_bluesky_client(handle: str, password: str):
    """Returns a cached authenticated client."""
    from utils.auth import login
    return login(handle, password)


@st.cache_resource(ttl=3600)
def get_version():
    """Get version from git commit hash (cached for 1 hour)."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parent),
        )
        if result.returncode == 0:
            return f"v{result.stdout.strip()}"
    except Exception:
        pass
    return "v1.0"


# =============================================================
# SESSION STATE INIT
# =============================================================

from core.bot_runner import BotRunner, StatsRefresher

if 'like_runner' not in st.session_state:
    st.session_state.like_runner = BotRunner()
if 'follow_runner' not in st.session_state:
    st.session_state.follow_runner = BotRunner()
if 'unfollow_runner' not in st.session_state:
    st.session_state.unfollow_runner = BotRunner()
if 'stats_refresher' not in st.session_state:
    st.session_state.stats_refresher = StatsRefresher()

for key, default in [
    ("handle", ""),
    ("target", ""),
    ("verified", False),
    ("profile_handle", ""),
    ("profile_followers", 0),
    ("client", None),
    ("active_page", "DASHBOARD"),
]:
    if key not in st.session_state:
        st.session_state[key] = default

# =============================================================
# LOADING SCREEN (first render)
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
    from views.login import render as render_login
    render_login(get_bluesky_client)

# =============================================================
# SIDEBAR NAVIGATION (shown only when verified)
# =============================================================

from core.bot_runner import any_bot_running, get_running_bot_name

with st.sidebar:
    version = get_version()
    st.markdown(f"""
    <div style="margin-bottom:32px">
        <span style="color:#00d4ff;font-size:14px;font-weight:700;font-family:'JetBrains Mono',monospace;letter-spacing:-0.5px">bluesky-engine</span>
        <span style="color:#555;font-size:14px;font-family:'JetBrains Mono',monospace"> {version}</span>
    </div>
    """, unsafe_allow_html=True)

    for nav_item in ["DASHBOARD", "LIKE", "FOLLOW", "UNFOLLOW", "EXPORT"]:
        is_active = st.session_state.active_page == nav_item
        if st.button(
            nav_item,
            key=f"nav_{nav_item}",
            use_container_width=True,
            type="primary" if is_active else "secondary"
        ):
            st.session_state.active_page = nav_item
            st.rerun()

    # Signout button
    st.markdown("<div style='margin-top:16px;border-top:1px solid #222;padding-top:16px'></div>", unsafe_allow_html=True)
    if any_bot_running():
        running_bot = get_running_bot_name()
        st.markdown(f"""
        <div style="font-size:11px;color:#fbbf24;font-family:'JetBrains Mono',monospace;padding:6px 8px;margin-bottom:8px">
            {running_bot} is running — stop it first
        </div>
        """, unsafe_allow_html=True)
        st.button("SIGN OUT", key="sidebar_signout", use_container_width=True, disabled=True)
    elif st.button("SIGN OUT", key="sidebar_signout", use_container_width=True):
        st.session_state.stats_refresher.stop()
        st.session_state.handle = ""
        st.session_state.verified = False
        st.session_state.client = None
        st.session_state.profile_handle = ""
        st.session_state.profile_followers = 0
        st.rerun()

page = st.session_state.active_page

# =============================================================
# PAGE ROUTING
# =============================================================

if page == "DASHBOARD":
    from views.dashboard import render as render_dashboard
    render_dashboard()

elif page == "LIKE":
    from bots.like_bot import like_bot_run
    from views.bot_page import render_bot_page

    account = [{"handle": st.session_state.handle, "client": st.session_state.get("client"), "enabled": True}]

    render_bot_page(
        page_title="Like",
        page_description="Like posts from non-followers randomly to get their attention",
        runner=st.session_state.like_runner,
        settings_key="like_settings",
        bot_func=like_bot_run,
        settings_fields=[
            {"key": "batch_size", "label": "BATCH SIZE", "min": 10, "max": 500, "default": 300, "step": 10,
             "help": "How many people to like posts from in one run. Start with 50 to test."},
            {"key": "likes_per_user", "label": "LIKES PER USER", "min": 1, "max": 5, "default": 2, "step": 1,
             "help": "How many posts to like per person. 2 is the sweet spot — enough to get noticed without being spammy."},
            {"key": "daily_cap", "label": "DAILY CAP", "min": 10, "max": 1000, "default": 800, "step": 10, "input_key": "like_daily_cap",
             "help": "Maximum likes per day across all runs. Keeps your account safe from Bluesky's rate limits."},
            {"key": "delay_min", "label": "MIN DELAY (sec)", "min": 1, "max": 60, "default": 5, "step": 1,
             "help": "Minimum seconds between likes. Lower is faster, but Bluesky may temporarily block your account if too fast."},
            {"key": "delay_max", "label": "MAX DELAY (sec)", "min": 1, "max": 60, "default": 10, "step": 1,
             "help": "Maximum seconds between likes. A random delay is picked between min and max to look natural."},
        ],
        build_bot_args=lambda s, t, e: (
            [account, s["batch_size"], s["likes_per_user"], s["delay_min"], s["delay_max"]],
            {}
        ),
        build_retry_args=lambda s: (s["account"], s["batch_size"], s["likes_per_user"], s["delay_min"], s["delay_max"]),
        format_results=lambda r: f"Like bot complete: {sum(x['liked'] for x in r)} liked, {sum(x['skipped'] for x in r)} skipped, {sum(x['errors'] for x in r)} errors",
        notification_name="Like bot",
        empty_state_html="""
        <div style="background:#111;border:1px solid #222;border-radius:2px;padding:24px;font-family:'JetBrains Mono',monospace">
            <div style="font-size:13px;color:#c8c8c8;margin-bottom:12px">Ready to run</div>
            <div style="font-size:12px;color:#888;line-height:1.8">
                This bot likes posts from people who don't follow you yet — a low-risk way to get on their radar.<br><br>
                <strong style="color:#c8c8c8">Recommended first run:</strong><br>
                · Batch size: 50 (start small to test)<br>
                · Likes per user: 2<br>
                · Daily cap: 200<br>
                · Delay: 5–10 sec<br><br>
                <span style="color:#666">Click RUN LIKE above to start.</span>
            </div>
        </div>
        """,
    )

elif page == "FOLLOW":
    from bots.follow_bot import follow_bot_run
    from views.bot_page import render_bot_page

    def build_follow_args(settings, target, exemptions):
        valid_accounts = [{
            "handle": st.session_state.handle,
            "client": st.session_state.get("client"),
            "target": target,
            "enabled": True
        }]
        return (
            [valid_accounts, settings["pull_limit"], settings["daily_cap"],
             settings["delay_min"], settings["delay_max"], settings["auto_like_count"]],
            {}
        )

    render_bot_page(
        page_title="Follow",
        page_description="Build your audience by following relevant accounts",
        runner=st.session_state.follow_runner,
        settings_key="follow_settings",
        bot_func=follow_bot_run,
        settings_fields=[
            {"key": "pull_limit", "label": "PULL LIMIT", "min": 10, "max": 500, "default": 300, "step": 10,
             "help": "How many of the target's followers to review before selecting who to follow. 200 is a good start."},
            {"key": "daily_cap", "label": "DAILY CAP", "min": 10, "max": 200, "default": 150, "step": 5,
             "help": "Maximum accounts to follow in one run. Keeps your account safe from Bluesky's rate limits."},
            {"key": "delay_min", "label": "MIN DELAY (sec)", "min": 1, "max": 60, "default": 5, "step": 1, "input_key": "follow_delay_min",
             "help": "Minimum seconds between follows. Lower is faster, but Bluesky may temporarily block your account if too fast."},
            {"key": "delay_max", "label": "MAX DELAY (sec)", "min": 1, "max": 60, "default": 15, "step": 1, "input_key": "follow_delay_max",
             "help": "Maximum seconds between follows. A random delay is picked between min and max to look natural."},
            {"key": "auto_like_count", "label": "AUTO-LIKE POSTS", "min": 0, "max": 5, "default": 2, "step": 1,
             "help": "Automatically like posts from each account you follow. Makes your follow feel genuine and increases follow-back chance. 0 = disabled."},
        ],
        build_bot_args=build_follow_args,
        build_retry_args=lambda s: (s["accounts"], s["pull_limit"], s["daily_cap"], s["delay_min"], s["delay_max"], s["auto_like_count"]),
        format_results=lambda r: f"Follow bot complete: {sum(x['followed'] for x in r)} followed, {sum(x['liked'] for x in r)} liked, {sum(x['errors'] for x in r)} errors",
        notification_name="Follow bot",
        has_target=True,
        empty_state_html="""
        <div style="background:#111;border:1px solid #222;border-radius:2px;padding:24px;font-family:'JetBrains Mono',monospace">
            <div style="font-size:13px;color:#c8c8c8;margin-bottom:12px">Ready to run</div>
            <div style="font-size:12px;color:#888;line-height:1.8">
                This bot follows followers of a target account. Pick someone in your niche with an engaged audience.<br><br>
                <strong style="color:#c8c8c8">Recommended first run:</strong><br>
                · Target: someone with 1K–50K followers in your niche<br>
                · Pull limit: 100<br>
                · Daily cap: 50 (start conservative)<br>
                · Auto-like: 2 (likes posts after following)<br><br>
                <span style="color:#666">Set a target account above, then click RUN FOLLOW.</span>
            </div>
        </div>
        """,
    )

elif page == "UNFOLLOW":
    from bots.unfollow_bot import unfollow_bot_run
    from views.bot_page import render_bot_page

    def build_unfollow_args(settings, target, exemptions):
        account = [{"handle": st.session_state.handle, "client": st.session_state.get("client"), "enabled": True}]
        return (
            [account, settings["days_threshold"], settings["daily_cap"],
             settings["delay_min"], settings["delay_max"], exemptions],
            {}
        )

    render_bot_page(
        page_title="Unfollow",
        page_description="Unfollow accounts that don't follow you back after X days",
        runner=st.session_state.unfollow_runner,
        settings_key="unfollow_settings",
        bot_func=unfollow_bot_run,
        settings_fields=[
            {"key": "days_threshold", "label": "DAYS THRESHOLD", "min": 1, "max": 365, "default": 30, "step": 1,
             "help": "Wait this many days before unfollowing non-followers. Gives people time to follow back. 30 days is a safe default."},
            {"key": "daily_cap", "label": "DAILY CAP", "min": 10, "max": 300, "default": 200, "step": 5, "input_key": "unfollow_daily_cap",
             "help": "Maximum accounts to unfollow in one run. Keeps your account safe from Bluesky's rate limits."},
            {"key": "delay_min", "label": "MIN DELAY (sec)", "min": 1, "max": 60, "default": 5, "step": 1, "input_key": "unfollow_delay_min",
             "help": "Minimum seconds between unfollows. Lower is faster, but Bluesky may temporarily block your account if too fast."},
            {"key": "delay_max", "label": "MAX DELAY (sec)", "min": 1, "max": 60, "default": 15, "step": 1, "input_key": "unfollow_delay_max",
             "help": "Maximum seconds between unfollows. A random delay is picked between min and max to look natural."},
        ],
        build_bot_args=build_unfollow_args,
        build_retry_args=lambda s: (s["account"], s["days_threshold"], s["daily_cap"], s["delay_min"], s["delay_max"], s["exemptions"]),
        format_results=lambda r: f"Unfollow bot complete: {sum(x['unfollowed'] for x in r)} unfollowed, {sum(x['skipped'] for x in r)} skipped, {sum(x['errors'] for x in r)} errors",
        notification_name="Unfollow bot",
        has_exemptions=True,
        empty_state_html="""
        <div style="background:#111;border:1px solid #222;border-radius:2px;padding:24px;font-family:'JetBrains Mono',monospace">
            <div style="font-size:13px;color:#c8c8c8;margin-bottom:12px">Ready to run</div>
            <div style="font-size:12px;color:#888;line-height:1.8">
                This bot unfollows accounts that haven't followed you back after X days. Keeps your follow ratio healthy.<br><br>
                <strong style="color:#c8c8c8">Recommended first run:</strong><br>
                · Days threshold: 30 (give people time to follow back)<br>
                · Daily cap: 100<br>
                · Delay: 5–15 sec<br>
                · Add exemptions for accounts you never want to unfollow<br><br>
                <span style="color:#666">Click RUN UNFOLLOW above to start.</span>
            </div>
        </div>
        """,
    )

elif page == "EXPORT":
    from views.export import render as render_export
    render_export()
