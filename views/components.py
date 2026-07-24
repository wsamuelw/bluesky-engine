"""
Shared UI components.
"""

import html
import streamlit as st


def render_metric_card(label, value, tooltip, colour="#c8c8c8", font_size="40px", subtitle=None):
    """Render a dashboard metric card."""
    safe_label = html.escape(label)
    safe_tooltip = html.escape(tooltip)
    subtitle_html = f'<div style="font-size:12px;color:#666;margin-top:8px">{subtitle}</div>' if subtitle else ""
    st.markdown(f"""
    <div style="background:#111;border:1px solid #222;border-radius:2px;padding:32px;text-align:center">
        <div style="font-size:12px;color:#999;text-transform:uppercase;letter-spacing:1px;margin-bottom:12px">
            {safe_label} <span style="cursor:help;color:#999;font-size:11px;vertical-align:super" data-tooltip="{safe_tooltip}">ⓘ</span>
        </div>
        <div style="font-size:{font_size};font-weight:700;color:{colour}">{value}</div>
        {subtitle_html}
    </div>
    """, unsafe_allow_html=True)


def render_loading_screen(message="Loading..."):
    """Render the branded loading screen with animated progress bar."""
    st.markdown(f"""
    <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;height:60vh">
        <span style="color:#00d4ff;font-size:28px;font-weight:700;font-family:'JetBrains Mono',monospace;letter-spacing:-1px">bluesky-engine</span>
        <div style="color:#888;font-size:13px;margin-top:12px;font-family:'JetBrains Mono',monospace">{message}</div>
        <div style="margin-top:20px;width:120px;height:3px;background:#222;border-radius:2px;overflow:hidden">
            <div style="width:40%;height:100%;background:#00d4ff;border-radius:2px;animation:pulse 1.2s ease-in-out infinite"></div>
        </div>
    </div>
    <style>
        @keyframes pulse {{
            0% {{transform:translateX(-100%)}}
            100% {{transform:translateX(350%)}}
        }}
    </style>
    """, unsafe_allow_html=True)
