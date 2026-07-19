"""
Follower/following stats helpers.
"""

from atproto import Client
from datetime import datetime, timezone
from utils.tracker import load_history, get_chart_data


def get_stats(handle: str, client: Client) -> dict:
    """
    Get follower, following, and engagement stats for an account.

    Args:
        handle: e.g. "alice.bsky.social"
        client: authenticated Client

    Returns:
        dict with followers, following, account_age_days, posts_per_day, engagement_rate, etc.
    """
    profile = client.app.bsky.actor.get_profile({"actor": handle})

    followers = profile.followers_count or 0
    following = profile.follows_count or 0
    posts_count = profile.posts_count or 0

    # Calculate account age
    account_age_days = 0
    posts_per_day = 0
    if profile.created_at:
        try:
            created = datetime.fromisoformat(profile.created_at.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            account_age_days = (now - created).days
            if account_age_days > 0:
                posts_per_day = round(posts_count / account_age_days, 1)
        except:
            pass

    # Calculate engagement metrics from recent posts
    engagement_rate = 0
    avg_likes_per_post = 0
    avg_reposts_per_post = 0
    try:
        feed = client.app.bsky.feed.get_author_feed({"actor": handle, "limit": 20})
        if feed.feed and followers > 0:
            total_engagement = 0
            total_likes = 0
            total_reposts = 0
            for item in feed.feed:
                likes = item.post.like_count or 0
                replies = item.post.reply_count or 0
                reposts = item.post.repost_count or 0
                total_engagement += likes + replies + reposts
                total_likes += likes
                total_reposts += reposts
            avg_engagement = total_engagement / len(feed.feed)
            engagement_rate = round((avg_engagement / followers) * 100, 2)
            avg_likes_per_post = round(total_likes / len(feed.feed), 1)
            avg_reposts_per_post = round(total_reposts / len(feed.feed), 1)
    except:
        pass

    # Calculate mutual follows (people you follow who follow you back)
    mutual_follows = 0
    try:
        following_set = set()
        cursor = None
        while True:
            params = {"actor": handle, "limit": 100}
            if cursor:
                params["cursor"] = cursor
            result = client.app.bsky.graph.get_follows(params)
            for user in result.follows:
                following_set.add(user.did)
            cursor = result.cursor
            if not cursor:
                break

        followers_set = set()
        cursor = None
        while True:
            params = {"actor": handle, "limit": 100}
            if cursor:
                params["cursor"] = cursor
            result = client.app.bsky.graph.get_followers(params)
            for user in result.followers:
                followers_set.add(user.did)
            cursor = result.cursor
            if not cursor:
                break

        mutual_follows = len(following_set & followers_set)
    except:
        pass

    # Calculate follower growth rate (7d)
    growth_rate_7d = 0
    try:
        history = load_history()
        chart_data = get_chart_data(history)
        if len(chart_data) >= 7:
            recent = chart_data[-7:]
            growth = recent[-1]["followers"] - recent[0]["followers"]
            growth_rate_7d = round(growth / 7, 1)
    except:
        pass

    return {
        "followers": followers,
        "following": following,
        "handle": handle,
        "account_age_days": account_age_days,
        "posts_per_day": posts_per_day,
        "engagement_rate": engagement_rate,
        "mutual_follows": mutual_follows,
        "avg_likes_per_post": avg_likes_per_post,
        "avg_reposts_per_post": avg_reposts_per_post,
        "growth_rate_7d": growth_rate_7d,
    }
