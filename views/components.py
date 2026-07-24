"""
Shared UI components.
"""

import streamlit as st


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
