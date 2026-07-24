"""
Dashboard page — metrics and stats.
"""

import streamlit as st
import streamlit.components.v1 as components
import time
from datetime import datetime
from utils.stats import get_stats
from utils.tracker import save_snapshot
from utils.constants import (
    FOLLOW_BACK_RATE_GOOD, FOLLOW_BACK_RATE_OK,
    ENGAGEMENT_RATE_GOOD, ENGAGEMENT_RATE_OK,
    NON_FOLLOWER_WARNING_RATIO, NON_FOLLOWER_WARNING_MIN,
)
from views.components import render_loading_screen, render_metric_card


def render():
    """Render the dashboard page."""
    if not st.session_state.verified:
        st.info("Please sign in to view dashboard.")
    elif st.session_state.stats_refresher.auth_expired:
        st.warning("Your session has expired. Please sign out and sign back in.")
    else:
        # Show loading screen on first fetch
        if "cached_stats" not in st.session_state:
            render_loading_screen("Fetching your data...")

            try:
                client = st.session_state.client
                stats = get_stats(st.session_state.handle, client)
                st.session_state.cached_stats = stats
                st.rerun()
            except Exception:
                st.error("Failed to fetch stats. Please try again.")
                st.stop()

        # Pick up fresh stats from background refresher (thread-safe)
        pending = st.session_state.stats_refresher.consume_pending_stats()
        if pending:
            st.session_state.cached_stats = pending

        # Load stats from cache
        try:
            stats = st.session_state.cached_stats

            followers = stats["followers"]
            following = stats["following"]
            posts_per_day = stats["posts_per_day"]
            engagement_rate = stats["engagement_rate"]
            reply_rate = stats["reply_rate"]
            repost_rate = stats["repost_rate"]
            avg_likes_per_post = stats["avg_likes_per_post"]
            follow_ratio = stats["follow_ratio"]
            non_followers = stats["non_followers"]

            follow_back_rate = (followers / following * 100) if following > 0 else 0

            # Determine colours
            if follow_back_rate >= FOLLOW_BACK_RATE_GOOD:
                fbr_color = "#4ade80"
            elif follow_back_rate >= FOLLOW_BACK_RATE_OK:
                fbr_color = "#fbbf24"
            else:
                fbr_color = "#f87171"

            if engagement_rate >= ENGAGEMENT_RATE_GOOD:
                er_color = "#4ade80"
            elif engagement_rate >= ENGAGEMENT_RATE_OK:
                er_color = "#fbbf24"
            else:
                er_color = "#f87171"

            # Avg likes/Post colour (based on absolute value)
            if avg_likes_per_post >= 10:
                alp_color = "#4ade80"
            elif avg_likes_per_post >= 3:
                alp_color = "#fbbf24"
            else:
                alp_color = "#f87171"

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

            # Last updated timestamp + manual refresh
            refresher = st.session_state.stats_refresher
            last_ts = refresher.last_updated
            if last_ts:
                time_str = last_ts.strftime("%I:%M %p").lstrip("0")
            else:
                time_str = datetime.now().strftime("%I:%M %p").lstrip("0")

            col_ts, col_btn = st.columns([6, 1])
            with col_ts:
                st.markdown(f"""
                <div style="font-size:11px;color:#555;font-family:'JetBrains Mono',monospace;margin-bottom:16px">
                    Last updated: {time_str} · Auto-refreshes every 5 min
                </div>
                """, unsafe_allow_html=True)
            with col_btn:
                if st.button("REFRESH", key="refresh_stats", use_container_width=True):
                    try:
                        stats = get_stats(st.session_state.handle, st.session_state.client)
                        st.session_state.cached_stats = stats
                        refresher._last_updated = datetime.now()
                        st.rerun()
                    except Exception:
                        st.error("Failed to refresh.")

            # Contextual guidance for edge cases
            if followers == 0:
                st.info("Your account has no followers yet. Start with the LIKE tab to warm up accounts, then use FOLLOW to grow.")
            elif non_followers > following * NON_FOLLOWER_WARNING_RATIO and following > NON_FOLLOWER_WARNING_MIN:
                st.markdown(f"""
                <div style="padding:10px 16px;background:#1a1500;border:1px solid #333;border-left:3px solid #fbbf24;border-radius:2px;margin-bottom:16px;font-size:12px;color:#c8c8c8;font-family:'JetBrains Mono',monospace">
                    High non-follower ratio ({non_followers:,} of {following:,}). Consider running the UNFOLLOW bot to clean up.
                </div>
                """, unsafe_allow_html=True)

            # SUCCESS METRICS
            st.markdown("""
            <div style="margin-bottom:16px;margin-top:16px">
                <span style="font-size:12px;text-transform:uppercase;letter-spacing:2px;color:#00d4ff;font-family:'JetBrains Mono',monospace;font-weight:600">Success Metrics</span>
                <span style="font-size:12px;color:#555;margin-left:12px;font-family:'JetBrains Mono',monospace">Are we winning?</span>
            </div>
            """, unsafe_allow_html=True)

            col1, col2, col3, col4 = st.columns(4)

            with col1:
                render_metric_card("Avg Likes/Post", avg_likes_per_post, "Average likes per post based on your last 20 posts. Higher = better content", alp_color, subtitle="per post")

            with col2:
                render_metric_card("Followers", f"{followers:,}", "Total accounts following you", subtitle=f"{posts_per_day} posts/day")

            with col3:
                render_metric_card("Engagement", f"{engagement_rate}%", "Average engagement (likes, replies, reposts) per post as % of followers, based on last 20 posts", er_color, subtitle="of followers")

            with col4:
                render_metric_card("Follow Ratio", f"{follow_ratio:.1f}x", "Followers ÷ Following. Higher = more credible account", subtitle="followers/following")

            # KEY DRIVERS
            st.markdown("""
            <div style="margin-bottom:16px;margin-top:16px">
                <span style="font-size:12px;text-transform:uppercase;letter-spacing:2px;color:#00d4ff;font-family:'JetBrains Mono',monospace;font-weight:600">Key Drivers</span>
                <span style="font-size:12px;color:#555;margin-left:12px;font-family:'JetBrains Mono',monospace">What do we change?</span>
            </div>
            """, unsafe_allow_html=True)

            col5, col6, col7, col8 = st.columns(4)

            with col5:
                render_metric_card("Follow-back Rate", f"{follow_back_rate:.1f}%", "% of accounts you follow who follow you back. Optimize who you follow", fbr_color, font_size="36px", subtitle="target: 20%+")

            with col6:
                render_metric_card("Posts/Day", posts_per_day, "Average posts per day. More posts = more engagement opportunities", font_size="36px", subtitle="target: 3+")

            with col7:
                render_metric_card("Reply Rate", f"{reply_rate}%", "Replies as % of total engagement. Higher = deeper conversations", font_size="36px", subtitle="target: 5%+")

            with col8:
                render_metric_card("Repost Rate", f"{repost_rate}%", "Reposts as % of total engagement. Higher = content spreading", font_size="36px", subtitle="target: 2%+")

        except Exception as e:
            st.error(f"Failed to fetch stats: {str(e)[:200]}")
