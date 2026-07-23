"""
Follower/following stats helpers.
"""

from atproto import Client
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from utils.tracker import load_history, get_chart_data


def _fetch_profile(client: Client, handle: str):
    """Fetch profile info."""
    return client.app.bsky.actor.get_profile({"actor": handle})


def _fetch_feed(client: Client, handle: str):
    """Fetch recent posts for engagement stats."""
    return client.app.bsky.feed.get_author_feed({"actor": handle, "limit": 20})


def _fetch_all_follows(client: Client, handle: str) -> set:
    """Fetch all follow DIDs (paginated, limit=100 per request)."""
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
    return following_set


def _fetch_all_followers(client: Client, handle: str) -> set:
    """Fetch all follower DIDs (paginated, limit=100 per request)."""
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
    return followers_set


def get_stats(handle: str, client: Client) -> dict:
    """
    Get follower, following, and engagement stats for an account.

    Args:
        handle: e.g. "alice.bsky.social"
        client: authenticated Client

    Returns:
        dict with followers, following, account_age_days, posts_per_day, engagement_rate, etc.
    """
    # Run all 4 API tasks in parallel
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {
            executor.submit(_fetch_profile, client, handle): "profile",
            executor.submit(_fetch_feed, client, handle): "feed",
            executor.submit(_fetch_all_follows, client, handle): "follows",
            executor.submit(_fetch_all_followers, client, handle): "followers",
        }

        results = {}
        for future in as_completed(futures):
            key = futures[future]
            try:
                results[key] = future.result()
            except Exception as e:
                print(f"[stats] Error fetching {key}: {e}")
                results[key] = None

    # Extract profile data
    profile = results.get("profile")
    if not profile:
        return {"error": "Failed to fetch profile"}

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
    reply_rate = 0
    repost_rate = 0
    avg_replies_per_post = 0
    feed = results.get("feed")
    if feed and feed.feed and followers > 0:
        try:
            total_engagement = 0
            total_replies = 0
            total_reposts = 0
            for item in feed.feed:
                likes = item.post.like_count or 0
                replies = item.post.reply_count or 0
                reposts = item.post.repost_count or 0
                total_engagement += likes + replies + reposts
                total_replies += replies
                total_reposts += reposts
            avg_engagement = total_engagement / len(feed.feed)
            engagement_rate = round((avg_engagement / followers) * 100, 2)
            avg_replies_per_post = round(total_replies / len(feed.feed), 1)
            # Reply rate: replies as % of total engagement
            if total_engagement > 0:
                reply_rate = round((total_replies / total_engagement) * 100, 1)
                repost_rate = round((total_reposts / total_engagement) * 100, 1)
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

    # Calculate followers/following ratio
    follow_ratio = round(followers / following, 2) if following > 0 else 0

    return {
        "followers": followers,
        "following": following,
        "handle": handle,
        "posts_per_day": posts_per_day,
        "engagement_rate": engagement_rate,
        "reply_rate": reply_rate,
        "repost_rate": repost_rate,
        "avg_replies_per_post": avg_replies_per_post,
        "growth_rate_7d": growth_rate_7d,
        "follow_ratio": follow_ratio,
        "non_followers": max(0, following - followers),
    }
