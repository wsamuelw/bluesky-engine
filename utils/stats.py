"""
Follower/following stats helpers.
"""

from atproto import Client
from datetime import datetime, timezone


def get_stats(handle: str, client: Client) -> dict:
    """
    Get follower, following, posts, and engagement stats for an account.

    Args:
        handle: e.g. "alice.bsky.social"
        client: authenticated Client

    Returns:
        dict with followers, following, ratio, posts_count, account_age_days, posts_per_day, engagement_rate
    """
    profile = client.app.bsky.actor.get_profile({"actor": handle})

    followers = profile.followers_count or 0
    following = profile.follows_count or 0
    posts_count = profile.posts_count or 0

    # Calculate ratio (followers:following)
    if followers > 0 and following > 0:
        ratio = round(followers / following, 2)
        ratio_str = f"{ratio}:1"
    elif followers > 0:
        ratio_str = f"{followers}:0"
    else:
        ratio_str = "N/A"

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
    most_liked_post = 0
    avg_likes_per_post = 0
    try:
        feed = client.app.bsky.feed.get_author_feed({"actor": handle, "limit": 20})
        if feed.feed and followers > 0:
            total_engagement = 0
            total_likes = 0
            for item in feed.feed:
                likes = item.post.like_count or 0
                replies = item.post.reply_count or 0
                reposts = item.post.repost_count or 0
                total_engagement += likes + replies + reposts
                total_likes += likes
                if likes > most_liked_post:
                    most_liked_post = likes
            avg_engagement = total_engagement / len(feed.feed)
            engagement_rate = round((avg_engagement / followers) * 100, 2)
            avg_likes_per_post = round(total_likes / len(feed.feed), 1)
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

    return {
        "followers": followers,
        "following": following,
        "ratio": ratio_str,
        "handle": handle,
        "posts_count": posts_count,
        "account_age_days": account_age_days,
        "posts_per_day": posts_per_day,
        "engagement_rate": engagement_rate,
        "mutual_follows": mutual_follows,
        "most_liked_post": most_liked_post,
        "avg_likes_per_post": avg_likes_per_post,
    }
