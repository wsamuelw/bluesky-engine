"""
Follower count tracker — stores daily snapshots for growth chart.
"""

import json
import os
from datetime import datetime

DATA_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "follower_history.json")


def load_history() -> dict:
    """
    Load follower history from JSON file.

    Returns:
        dict with dates as keys, e.g.
        {
            "2026-07-18": {"followers": 1247, "following": 7842},
            "2026-07-19": {"followers": 1262, "following": 7827},
        }
    """
    if not os.path.exists(DATA_FILE):
        return {}

    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def save_snapshot(followers: int, following: int) -> None:
    """
    Save today's follower/following count.

    Only saves if today's data doesn't exist yet (one snapshot per day).
    """
    history = load_history()
    today = datetime.now().strftime("%Y-%m-%d")

    # Only save if today's data doesn't exist
    if today not in history:
        history[today] = {
            "followers": followers,
            "following": following,
        }

        # Ensure data directory exists
        os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)

        with open(DATA_FILE, "w") as f:
            json.dump(history, f, indent=2)


def get_chart_data(history: dict) -> list:
    """
    Convert history dict to sorted list for charting.

    Returns:
        list of dicts sorted by date, e.g.
        [
            {"date": "2026-07-18", "followers": 1247, "following": 7842},
            {"date": "2026-07-19", "followers": 1262, "following": 7827},
        ]
    """
    data = []
    for date_str in sorted(history.keys()):
        entry = history[date_str]
        data.append({
            "date": date_str,
            "followers": entry.get("followers", 0),
            "following": entry.get("following", 0),
        })
    return data
