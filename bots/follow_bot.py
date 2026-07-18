"""
Follow Bot — copies followers from target accounts.

Uses synchronous atproto client for Streamlit compatibility.
Passes a callback function for live log updates.
"""

import random
import time
from datetime import datetime

from atproto import Client


def ts() -> str:
    """Current timestamp for log output."""
    return datetime.now().strftime("%H:%M:%S")


def follow_bot_run(accounts, pull_limit, daily_cap, delay_min, delay_max, auto_like, log_callback=None):
    """
    Run follow bot on all enabled accounts.

    Args:
        accounts: list of account dicts with handle, password, target, enabled
        pull_limit: max followers to pull from target
        daily_cap: max follows per account per run
        delay_min: min seconds between follows
        delay_max: max seconds between follows
        auto_like: bool, like posts after following
        log_callback: function to call with each log line

    Returns:
        list of result dicts
    """
    def log(line):
        if log_callback:
            log_callback(line)

    enabled = [a for a in accounts if a.get("enabled", True)]

    log("=" * 55)
    log(f"STARTING {len(enabled)} ACCOUNTS")
    log("=" * 55)

    results = []

    for acc in enabled:
        result = _run_single_account(acc, pull_limit, daily_cap, delay_min, delay_max, auto_like, log_callback)
        results.append(result)

    # Summary
    log("")
    log("=" * 55)
    log("COMPLETE")
    log("=" * 55)

    total_followed = 0
    total_liked = 0
    total_errors = 0

    for r in results:
        log(f"  @{r['handle']}: {r['followed']} followed, {r['liked']} liked, {r['errors']} errors")
        total_followed += r["followed"]
        total_liked += r["liked"]
        total_errors += r["errors"]

    log("")
    log(f"  TOTAL: {total_followed} followed, {total_liked} liked, {total_errors} errors")
    log(f"  Finished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    return results


def _run_single_account(account, pull_limit, daily_cap, delay_min, delay_max, auto_like, log_callback=None):
    """
    Run follow bot for a single account.

    Returns:
        dict with handle, followed, liked, errors
    """
    def log(line):
        if log_callback:
            log_callback(line)

    handle = account["handle"]
    password = account["password"]
    target = account.get("target", "")

    if not target:
        log(f"[{ts()}] ERR  [{handle}] No target account configured")
        return {"handle": handle, "followed": 0, "liked": 0, "errors": 1}

    # Login
    try:
        client = Client()
        profile = client.login(handle, password)
        log(f"[{ts()}] OK   [{handle}] Authenticated")
    except Exception as e:
        log(f"[{ts()}] ERR  [{handle}] Auth failed: {e}")
        return {"handle": handle, "followed": 0, "liked": 0, "errors": 1}

    # Get currently following (to avoid duplicates)
    my_did = profile.did
    all_following = set()
    cursor = None
    while True:
        params = {"actor": handle, "limit": 100}
        if cursor:
            params["cursor"] = cursor
        result = client.app.bsky.graph.get_follows(params)
        for user in result.follows:
            all_following.add(user.did)
        cursor = result.cursor
        if not cursor:
            break

    # Pull target's followers
    log(f"[{ts()}] INFO [{handle}] Pulling followers of @{target}...")
    target_followers = []
    cursor = None
    seen_dids = set()

    while len(target_followers) < pull_limit:
        params = {"actor": target, "limit": 100}
        if cursor:
            params["cursor"] = cursor
        result = client.app.bsky.graph.get_followers(params)

        for user in result.followers:
            # Skip if already followed, already seen, or self
            if user.did in all_following or user.did in seen_dids or user.did == my_did:
                continue
            seen_dids.add(user.did)
            target_followers.append({"did": user.did, "handle": user.handle})

        cursor = result.cursor
        if not cursor:
            break

    target_followers = target_followers[:pull_limit]
    log(f"[{ts()}] OK   [{handle}] {len(target_followers)} new targets")

    if not target_followers:
        log(f"[{ts()}] WARN [{handle}] No new targets. Skipping.")
        return {"handle": handle, "followed": 0, "liked": 0, "errors": 0}

    # Follow loop
    followed = 0
    liked = 0
    errors = 0

    for i, user in enumerate(target_followers):
        if followed >= daily_cap:
            log(f"[{ts()}] WARN [{handle}] Daily cap reached ({daily_cap}). Stopping.")
            break

        did = user["did"]
        user_handle = user["handle"]

        try:
            client.follow(did)
            followed += 1
            log(f"[{ts()}] OK   [{handle}] [{followed}/{daily_cap}] Followed @{user_handle}")

            # Auto-like posts after following
            if auto_like:
                l = _like_recent_posts(client, did, max_likes=2)
                liked += l
                if l > 0:
                    log(f"[{ts()}] OK   [{handle}]   -> Liked {l} posts")

        except Exception as e:
            errors += 1
            log(f"[{ts()}] ERR  [{handle}] @{user_handle}: {str(e)[:200]}")
            if "rate" in str(e).lower() or "429" in str(e):
                log(f"[{ts()}] WARN [{handle}] Rate limited. Pausing 60s...")
                time.sleep(60)

        # Delay between follows
        if i < len(target_followers) - 1:
            delay = random.uniform(delay_min, delay_max)
            time.sleep(delay)

    return {"handle": handle, "followed": followed, "liked": liked, "errors": errors}


def _like_recent_posts(client, target_did, max_likes=2):
    """
    Like 1-2 of a user's recent posts after following them.

    Returns:
        int: number of posts liked
    """
    liked = 0
    try:
        feed = client.app.bsky.feed.get_author_feed({"actor": target_did, "limit": 5})
        for item in feed.feed[:max_likes]:
            try:
                client.like(item.post.uri, item.post.cid)
                liked += 1
                time.sleep(random.uniform(1, 3))
            except:
                pass
    except:
        pass
    return liked
