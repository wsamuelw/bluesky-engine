"""
Follower/following stats helpers.
"""

from atproto import Client


def get_stats(handle: str, client: Client) -> dict:
    """
    Get follower and following counts for an account.

    Args:
        handle: e.g. "alice.bsky.social"
        client: authenticated Client

    Returns:
        dict with followers, following, ratio
    """
    profile = client.app.bsky.actor.get_profile({"actor": handle})

    followers = profile.followers_count or 0
    following = profile.follows_count or 0

    # Calculate ratio (followers:following)
    # Higher is better (more followers per following)
    if followers > 0 and following > 0:
        ratio = round(followers / following, 2)
        ratio_str = f"{ratio}:1"
    elif followers > 0:
        ratio_str = f"{followers}:0"
    else:
        ratio_str = "N/A"

    return {
        "followers": followers,
        "following": following,
        "ratio": ratio_str,
        "handle": handle,
    }
