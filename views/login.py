"""
Login page — authentication form.
"""

import streamlit as st
from atproto.exceptions import AtProtocolError


def render(get_bluesky_client):
    """Render the login page."""
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
                        border-radius:2px;margin-bottom:16px;font-size:13px;color:#f87171;font-family:'JetBrains Mono',monospace">
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
        <div style="text-align:center;margin-top:24px;font-size:10px;color:#777;font-family:'JetBrains Mono',monospace">
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
            import html
            handle = st.session_state.login_handle.strip()
            password = st.session_state.login_password.strip()

            if not handle or not password:
                st.session_state["login_error"] = "Please enter both handle and app password."
                st.rerun()
            elif "." not in handle:
                st.session_state["login_error"] = f"Invalid handle '{html.escape(handle)}'. Use full format like alice.bsky.social"
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
                    # Start background stats refresher
                    from utils.stats import get_stats
                    st.session_state.stats_refresher.start(handle, client, get_stats)
                    st.rerun()
                except AtProtocolError:
                    st.session_state["login_error"] = "Authentication failed. Check your handle and app password."
                    st.rerun()
                except Exception:
                    st.session_state["login_error"] = "Something went wrong. Please try again."
                    st.rerun()

    st.stop()
