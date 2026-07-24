"""
Shared constants for bluesky-engine.
"""

# API
API_LIMIT = 100  # Max items per Bluesky API request

# Timing
STATS_REFRESH_INTERVAL = 300  # 5 minutes between background stats refreshes
RATE_LIMIT_PAUSE = 60  # Seconds to pause on rate limit (429)
INTERRUPT_TICK = 0.5  # Seconds between stop-check ticks during delays

# Display
LOG_WINDOW = 50  # Number of log lines to show in live panel

# Dashboard thresholds
FOLLOW_BACK_RATE_GOOD = 20  # % threshold for green follow-back rate
FOLLOW_BACK_RATE_OK = 10  # % threshold for amber follow-back rate
ENGAGEMENT_RATE_GOOD = 5  # % threshold for green engagement rate
ENGAGEMENT_RATE_OK = 2  # % threshold for amber engagement rate
NON_FOLLOWER_WARNING_RATIO = 0.8  # Warn if non-followers exceed this % of following
NON_FOLLOWER_WARNING_MIN = 100  # Minimum following count to trigger warning
