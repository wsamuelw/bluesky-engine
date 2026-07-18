"""
Like Bot — likes posts from non-followers.

Extracted from like_bot.md, refactored to yield log lines
instead of printing (for Streamlit live display).
"""

import random
import asyncio
from datetime import datetime

from atproto import AsyncClient


def ts() -> str:
    """Current timestamp for log output."""
    return datetime.now().strftime("%H:%M:%S")


async def like_user_posts(client, user_did, user_handle, max_likes, delay_min, delay_max):
    """
    Like 1-2 recent posts from a single user.

    Yields log lines for Streamlit display.
    Returns number of posts liked.
    """
    liked = 0

    try:
        feed = await client.app.bsky.feed.get_author_feed({
            "actor": user_did,
            "limit": 5
        })

        if not feed.feed:
            yield f"[{ts()}] SKIP @{user_handle} — no posts"
            return

        # Grab extra posts in case some fail, shuffle for randomness
        posts = feed.feed[:max_likes + 2]
        random.shuffle(posts)
        posts = posts[:max_likes]

        for item in posts:
            try:
                await client.like(item.post.uri, item.post.cid)
                liked += 1
                delay = random.uniform(delay_min, delay_max)
                await asyncio.sleep(delay)
            except Exception as e:
                err = str(e).lower()
                if "already" in err:
                    pass  # already liked, skip
                else:
                    yield f"[{ts()}] ERR  liking post: {str(e)[:60]}"

    except Exception as e:
        yield f"[{ts()}] ERR  fetching posts for @{user_handle}: {str(e)[:60]}"

    return liked


async def like_non_followers(account, batch_size, likes_per_user, delay_min, delay_max):
    """
    Main like loop for a single account.

    Steps:
    1. Login
    2. Pull following list
    3. Pull followers list
    4. Find non-followers (following - followers)
    5. Randomly sample batch_size users
    6. Like 1-2 posts from each

    Yields log lines for Streamlit display.
    Returns results dict.
    """
    handle = account["handle"]
    password = account["password"]

    # Login
    try:
        client = AsyncClient()
        profile = await client.login(handle, password)
        yield f"[{ts()}] OK   [{handle}] Authenticated"
    except Exception as e:
        yield f"[{ts()}] ERR  [{handle}] Auth failed: {e}"
        return {"handle": handle, "liked": 0, "skipped": 0, "errors": 1}

    # Pull following
    yield f"[{ts()}] INFO [{handle}] Pulling following list..."
    following = set()
    cursor = None
    while True:
        params = {"actor": handle, "limit": 100}
        if cursor:
            params["cursor"] = cursor
        result = await client.app.bsky.graph.get_follows(params)
        for user in result.follows:
            following.add(user.did)
        cursor = result.cursor
        if not cursor:
            break
    yield f"[{ts()}] OK   [{handle}] Following {len(following)} accounts"

    # Pull followers
    yield f"[{ts()}] INFO [{handle}] Pulling followers list..."
    followers = set()
    cursor = None
    while True:
        params = {"actor": handle, "limit": 100}
        if cursor:
            params["cursor"] = cursor
        result = await client.app.bsky.graph.get_followers(params)
        for user in result.followers:
            followers.add(user.did)
        cursor = result.cursor
        if not cursor:
            break
    yield f"[{ts()}] OK   [{handle}] {len(followers)} followers"

    # Find non-followers
    non_followers = following - followers
    yield f"[{ts()}] OK   [{handle}] {len(non_followers)} non-followers"

    if not non_followers:
        yield f"[{ts()}] WARN [{handle}] No non-followers. Skipping."
        return {"handle": handle, "liked": 0, "skipped": 0, "errors": 0}

    # Random sample
    sample = list(non_followers)
    random.shuffle(sample)
    sample = sample[:batch_size]
    yield f"[{ts()}] OK   [{handle}] Randomly selected {len(sample)} users to like"

    # Like loop
    liked = 0
    skipped = 0
    errors = 0

    for i, user_did in enumerate(sample):
        # Fetch handle for logging
        try:
            profile_info = await client.app.bsky.actor.get_profile({"actor": user_did})
            user_handle = profile_info.handle
        except:
            user_handle = user_did[:20] + "..."

        try:
            l = await like_user_posts(
                client, user_did, user_handle,
                max_likes=likes_per_user,
                delay_min=delay_min,
                delay_max=delay_max
            )
            if l and l > 0:
                liked += l
                yield f"[{ts()}] OK   [{handle}] [{i+1}/{len(sample)}] Liked {l} posts from @{user_handle}"
            else:
                skipped += 1
        except Exception as e:
            errors += 1
            yield f"[{ts()}] ERR  [{handle}] @{user_handle}: {str(e)[:60]}"

        # Delay between users
        if i < len(sample) - 1:
            delay = random.uniform(delay_min, delay_max)
            await asyncio.sleep(delay)

    return {"handle": handle, "liked": liked, "skipped": skipped, "errors": errors}


async def run_all(accounts, batch_size, likes_per_user, delay_min, delay_max):
    """
    Run like bot on all enabled accounts in parallel.

    Yields log lines for Streamlit display.
    Returns list of result dicts.
    """
    enabled = [a for a in accounts if a.get("enabled", True)]

    yield "=" * 55
    yield f"STARTING {len(enabled)} ACCOUNTS"
    yield "=" * 55

    # Run all accounts concurrently
    # Note: we collect results from generators
    results = []
    for acc in enabled:
        result = None
        async for line in like_non_followers(acc, batch_size, likes_per_user, delay_min, delay_max):
            if isinstance(line, dict):
                result = line
            else:
                yield line
        if result:
            results.append(result)

    # Summary
    yield ""
    yield "=" * 55
    yield "COMPLETE"
    yield "=" * 55

    total_liked = 0
    total_skipped = 0
    total_errors = 0

    for r in results:
        yield f"  @{r['handle']}: {r['liked']} liked, {r['skipped']} skipped, {r['errors']} errors"
        total_liked += r["liked"]
        total_skipped += r["skipped"]
        total_errors += r["errors"]

    yield ""
    yield f"  TOTAL: {total_liked} liked, {total_skipped} skipped, {total_errors} errors"
    yield f"  Finished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

    return results
