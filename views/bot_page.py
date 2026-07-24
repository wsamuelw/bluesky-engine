"""
Generic bot page renderer — shared by Like, Follow, and Unfollow bots.
"""

import streamlit as st
import streamlit.components.v1 as components
from utils.constants import LOG_WINDOW


def send_notification(title: str, body: str):
    """Send a browser notification if permission is granted."""
    components.html(f"""
    <script>
    if ("Notification" in window && Notification.permission === "granted") {{
        new Notification("{title}", {{body: "{body}"}});
    }}
    </script>
    """, height=0)


@st.fragment(run_every=2)
def live_log_panel(runner):
    """Self-refreshing log panel that doesn't freeze the UI."""
    logs = runner.get_logs()
    progress = runner.get_progress()

    # Show progress counter if available
    if progress["total"] > 0:
        elapsed = runner.get_elapsed_seconds()
        elapsed_min = int(elapsed // 60)
        elapsed_sec = int(elapsed % 60)

        if progress["completed"] > 0:
            rate = elapsed / progress["completed"]
            remaining = rate * (progress["total"] - progress["completed"])
            eta_min = int(remaining // 60)
            eta_sec = int(remaining % 60)
            eta_str = f"{eta_min}:{eta_sec:02d}"
        else:
            eta_str = "calculating..."

        st.markdown(f"""
        <div style="padding:8px 12px;background:#111;border:1px solid #222;border-radius:2px;margin-bottom:10px;font-size:12px;color:#888;font-family:'JetBrains Mono',monospace">
            Progress: <strong style="color:#00d4ff">{progress['completed']}</strong> / {progress['total']}
            · Elapsed: {elapsed_min}:{elapsed_sec:02d}
            · ETA: ~{eta_str}
        </div>
        """, unsafe_allow_html=True)

    if logs:
        log_text = "\n".join(reversed(logs[-LOG_WINDOW:]))
        st.code(log_text, language="bash")
    else:
        st.code("Starting bot...", language="bash")
    if not runner.running:
        st.rerun()


def classify_error(error):
    """Classify error into user-friendly message."""
    error_msg = error.lower()
    if "auth" in error_msg or "invalid" in error_msg or "password" in error_msg:
        return f"Authentication failed: {error}. Sign out and sign back in to update your credentials."
    elif "rate" in error_msg or "429" in error_msg:
        return f"Rate limited: {error}. Wait a few minutes and try again."
    elif "timeout" in error_msg or "connection" in error_msg:
        return f"Network error: {error}. Check your connection and try again."
    else:
        return f"Bot error: {error}"


def render_bot_page(
    page_title,
    page_description,
    runner,
    settings_key,
    bot_func,
    settings_fields,
    build_bot_args,
    build_retry_args,
    format_results,
    notification_name,
    empty_state_html,
    has_target=False,
    has_exemptions=False,
):
    """
    Render a generic bot page.

    Args:
        page_title: Title shown at top of page (e.g., "Like")
        page_description: Description text below title
        runner: BotRunner instance
        settings_key: Session state key for settings dict
        bot_func: The bot function to call
        settings_fields: List of dicts defining each setting field:
            [{"key": "batch_size", "label": "BATCH SIZE", "min": 10, "max": 500,
              "default": 300, "step": 10, "help": "...", "input_key": None}]
        build_bot_args: func(settings, target, exemptions) -> (args, kwargs) for runner.start()
        build_retry_args: func(saved_settings) -> (args, kwargs) for retry
        format_results: func(results) -> str (success message)
        notification_name: Name shown in browser notifications
        empty_state_html: HTML string for empty state
        has_target: Whether to show target account input
        has_exemptions: Whether to show exemptions textarea
    """
    st.markdown(f"""
    <div style="margin-bottom:20px">
        <span style="font-size:12px;text-transform:uppercase;letter-spacing:2px;color:#00d4ff;font-weight:600">{page_title}</span>
        <br>
        <span style="font-size:13px;color:#888">{page_description}</span>
    </div>
    """, unsafe_allow_html=True)

    if not st.session_state.verified:
        st.warning("Please sign in first.")
        return

    # Target input (if applicable)
    target = None
    if has_target:
        st.markdown("""
        <div style="margin-bottom:10px">
            <span style="font-size:11px;text-transform:uppercase;letter-spacing:2px;color:#888">Assign Target Account</span>
        </div>
        """, unsafe_allow_html=True)

        target = st.text_input(
            "TARGET ACCOUNT",
            value=st.session_state.get("target", ""),
            placeholder="karpathy.bsky.social",
            key="follow_target",
        )
        st.session_state.target = target

    # Settings section
    st.markdown("""
    <div style="margin-top:20px;margin-bottom:10px">
        <span style="font-size:11px;text-transform:uppercase;letter-spacing:2px;color:#888">Bot Settings</span>
    </div>
    """, unsafe_allow_html=True)

    # Initialize defaults
    if settings_key not in st.session_state:
        st.session_state[settings_key] = {}

    for field in settings_fields:
        if field["key"] not in st.session_state[settings_key]:
            st.session_state[settings_key][field["key"]] = field["default"]

    # Render settings columns
    cols = st.columns(len(settings_fields))
    settings = {}
    for i, field in enumerate(settings_fields):
        with cols[i]:
            input_key = field.get("input_key")
            kwargs = {
                "min_value": field["min"],
                "max_value": field["max"],
                "value": st.session_state[settings_key][field["key"]],
                "step": field["step"],
                "help": field["help"],
            }
            if input_key:
                kwargs["key"] = input_key
            settings[field["key"]] = st.number_input(field["label"], **kwargs)

    # Persist settings
    st.session_state[settings_key] = settings

    # Exemptions (if applicable)
    exemptions = []
    if has_exemptions:
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
            placeholder="karpathy.bsky.social\nelonmusk.bsky.social\nnaval.bsky.social",
        )
        exemptions = [e.strip() for e in exemptions_text.split("\n") if e.strip()]

    # Action buttons
    col_btn, col_spacer = st.columns([1, 3])
    with col_btn:
        if runner.running:
            st.button("RUNNING...", key=f"{settings_key}_running", use_container_width=True, disabled=True)
            if st.button("STOP", key=f"stop_{settings_key}", use_container_width=True, type="primary"):
                runner.stop()
                st.rerun()
        else:
            run_clicked = st.button(f"RUN {page_title.upper()}", key=f"run_{settings_key}", use_container_width=True)

    # Live log panel
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

    # Run the bot
    if not runner.running and run_clicked:
        from core.bot_runner import any_bot_running, get_running_bot_name

        if any_bot_running():
            running_bot = get_running_bot_name()
            st.error(f"Cannot start {page_title} — {running_bot} is already running. Stop it first or wait for it to finish.")
        elif has_target:
            target = st.session_state.get("target", "").strip()
            if not target:
                st.error("No target configured. Add a target account.")
            elif "." not in target:
                st.error(f"Invalid target @{target}. Must be a full handle like 'karpathy.bsky.social'")
            else:
                args, kwargs = build_bot_args(settings, target, exemptions)
                retry_key = f"{settings_key}_retry"
                st.session_state[retry_key] = {"args": args, "kwargs": kwargs}
                runner.start(bot_func, *args, **kwargs)
                st.rerun()
        else:
            args, kwargs = build_bot_args(settings, target, exemptions)
            retry_key = f"{settings_key}_retry"
            st.session_state[retry_key] = {"args": args, "kwargs": kwargs}
            runner.start(bot_func, *args, **kwargs)
            st.rerun()

    # Bot running — show live logs
    if runner.running:
        live_log_panel(runner)

    # Bot finished — show results
    if not runner.running:
        results = runner.get_results()
        error = runner.get_error()

        if error:
            st.error(classify_error(error))
            if st.button("RETRY", key=f"retry_{settings_key}"):
                retry_key = f"{settings_key}_retry"
                saved = st.session_state.get(retry_key, {})
                if saved:
                    runner.start(bot_func, *saved["args"], **saved["kwargs"])
                    st.rerun()
            else:
                runner.clear()
        elif results:
            msg = format_results(results)
            if runner.stop_requested:
                st.warning(msg)
                send_notification("bluesky-engine", f"{notification_name} stopped")
            else:
                st.success(msg)
                send_notification("bluesky-engine", f"{notification_name} complete")
            runner.clear()

        logs = runner.get_logs()
        if logs:
            log_text = "\n".join(logs[-LOG_WINDOW:])
            log_placeholder.code(log_text, language="bash")
        else:
            log_placeholder.markdown(empty_state_html, unsafe_allow_html=True)
