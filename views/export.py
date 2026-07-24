"""
Export page — follower profile export.
"""

import streamlit as st
import json
from datetime import datetime


def render():
    """Render the export page."""
    st.markdown("""
    <div style="margin-bottom:20px">
        <span style="font-size:12px;text-transform:uppercase;letter-spacing:2px;color:#00d4ff;font-weight:600">Export</span>
        <br>
        <span style="font-size:13px;color:#888">Export follower profiles for AI analysis</span>
    </div>
    """, unsafe_allow_html=True)

    if not st.session_state.verified:
        st.warning("Please sign in first.")
        return

    st.markdown("""
    <div style="margin-bottom:16px">
        <span style="font-size:11px;text-transform:uppercase;letter-spacing:2px;color:#888">Export Follower Profiles</span>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div style="font-size:13px;color:#888;margin-bottom:20px">
        Extract all follower profiles (handle, bio, followers, following, etc.) and download as JSON.
        <br>Use with Claude, ChatGPT, or other AI tools to analyze your audience.
    </div>
    """, unsafe_allow_html=True)

    col_btn, col_spacer = st.columns([1, 3])
    with col_btn:
        export_clicked = st.button("EXPORT PROFILES", use_container_width=True)

    if export_clicked:
        try:
            client = st.session_state.client
            handle = st.session_state.handle

            followers = []
            cursor = None
            progress_placeholder = st.empty()

            while True:
                params = {"actor": handle, "limit": 100}
                if cursor:
                    params["cursor"] = cursor
                result = client.app.bsky.graph.get_followers(params)

                for user in result.followers:
                    followers.append({
                        "handle": user.handle,
                        "display_name": user.display_name or "",
                        "bio": user.description or "",
                    })

                progress_placeholder.markdown(f"""
                <div style="padding:8px 12px;background:#111;border:1px solid #222;border-radius:2px;font-size:12px;color:#888;font-family:'JetBrains Mono',monospace">
                    Fetching profiles... <strong style="color:#00d4ff">{len(followers)}</strong> collected
                </div>
                """, unsafe_allow_html=True)

                cursor = result.cursor
                if not cursor:
                    break

            progress_placeholder.empty()

            export_data = {
                "exported_at": datetime.now().isoformat(),
                "account": handle,
                "total_followers": len(followers),
                "followers": followers,
            }

            json_str = json.dumps(export_data, indent=2, ensure_ascii=False)

            col1, col2 = st.columns(2)
            with col1:
                st.metric("Total Followers", len(followers))
            with col2:
                bios_count = sum(1 for f in followers if f["bio"])
                st.metric("With Bio", bios_count)

            st.download_button(
                label="DOWNLOAD JSON",
                data=json_str,
                file_name=f"followers_{handle}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json",
                use_container_width=True,
            )

            st.markdown("""
            <div style="margin-top:20px;margin-bottom:10px">
                <span style="font-size:11px;text-transform:uppercase;letter-spacing:2px;color:#888">Preview (first 5)</span>
            </div>
            """, unsafe_allow_html=True)

            import html
            for f in followers[:5]:
                safe_handle = html.escape(f['handle'])
                safe_name = html.escape(f['display_name'])
                safe_bio = html.escape(f['bio'][:100])
                st.markdown(f"""
                <div style="background:#111;border:1px solid #222;border-radius:2px;padding:12px;margin-bottom:8px">
                    <div style="font-size:13px;color:#c8c8c8;font-weight:600">@{safe_handle}</div>
                    <div style="font-size:12px;color:#888;margin-top:4px">{safe_name}</div>
                    <div style="font-size:12px;color:#666;margin-top:4px">{safe_bio}{'...' if len(f['bio']) > 100 else ''}</div>
                </div>
                """, unsafe_allow_html=True)

        except Exception as e:
            st.error(f"Failed to export profiles: {str(e)[:200]}")
