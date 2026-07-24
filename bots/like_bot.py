"""
Like Bot — likes posts from non-followers.

Uses synchronous atproto client for Streamlit compatibility.
Passes a callback function for live log updates.
"""

import random
import time
from datetime import datetime
from utils.pagination import paginate_follows, paginate_followers
from core.callbacks import BotCallbacks

from atproto import Client


def ts() -> str:
    """Current timestamp for log output."""
    return datetime.now().strftime("%H:%M:%S")


def like_bot_run(accounts, batch_size, likes_per_user, delay_min, delay_max, log_callback=None, stop_check=None, progress_callback=None):
    """
    Run like bot on all enabled accounts.

    Args:
        accounts: list of account dicts with handle, password, enabled
        batch_size: max non-followers to like per account
        likes_per_user: how many posts to like per person
        delay_min: min seconds between likes
        delay_max: max seconds between likes
        log_callback: function to call with each log line (for live display)
        stop_check: function that returns True if bot should stop
        progress_callback: function to call with (completed, total) for progress tracking

    Returns:
        list of result dicts
    """
    def log(line):
        if log_callback:
            log_callback(line)

    def should_stop():
        if stop_check:
            return stop_check()
        return False

    def update_progress(completed, total):
        if progress_callback:
            progress_callback(completed, total)

    enabled = [a for a in accounts if a.get("enabled", True)]

    results = []

    for acc in enabled:
        if should_stop():
            log("Stop requested. Halting...")
            break
        result = _run_single_account(acc, batch_size, likes_per_user, delay_min, delay_max, log_callback, stop_check, progress_callback)
        results.append(result)

    # Summary
    log("")
    log("=" * 55)
    log("COMPLETE")
    log("=" * 55)

    total_liked = 0
    total_skipped = 0
    total_errors = 0

    for r in results:
        log(f"  @{r['handle']}: {r['liked']} liked, {r['skipped']} skipped, {r['errors']} errors")
        total_liked += r["liked"]
        total_skipped += r["skipped"]
        total_errors += r["errors"]

    log("")
    log(f"  TOTAL: {total_liked} liked, {total_skipped} skipped, {total_errors} errors")
    log(f"  Finished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    return results


def _run_single_account(account, batch_size, likes_per_user, delay_min, delay_max, log_callback=None, stop_check=None, progress_callback=None):
    """
    Run like bot for a single account.

    Returns:
        dict with handle, liked, skipped, errors
    """
    cb = BotCallbacks(log_callback=log_callback, stop_check=stop_check, progress_callback=progress_callback)
    log = cb.log
    should_stop = cb.should_stop
    update_progress = cb.update_progress

    handle = account["handle"]
    password = account.get("password", "")
    client = account.get("client")

    # Login if no client provided
    if not client:
        try:
            client = Client()
            client.login(handle, password)
            log(f"[{ts()}] OK   [{handle}] Authenticated")
        except Exception as e:
            log(f"[{ts()}] ERR  [{handle}] Auth failed: {e}")
            return {"handle": handle, "liked": 0, "skipped": 0, "errors": 1}
    else:
        log(f"[{ts()}] OK   [{handle}] Using cached client")

    # Pull following (store DID → handle for logging)
    log(f"[{ts()}] INFO [{handle}] Pulling following list...")
    following = {user.did: user.handle for user in paginate_follows(client, handle)}
    log(f"[{ts()}] OK   [{handle}] Following {len(following)} accounts")

    # Pull followers
    log(f"[{ts()}] INFO [{handle}] Pulling followers list...")
    followers = set(user.did for user in paginate_followers(client, handle))
    log(f"[{ts()}] OK   [{handle}] {len(followers)} followers")

    # Find non-followers
    non_followers = set(following.keys()) - followers
    log(f"[{ts()}] OK   [{handle}] {len(non_followers)} non-followers")

    if not non_followers:
        log(f"[{ts()}] WARN [{handle}] No non-followers. Skipping.")
        return {"handle": handle, "liked": 0, "skipped": 0, "errors": 0}

    # Random sample
    sample = list(non_followers)
    random.shuffle(sample)
    sample = sample[:batch_size]
    log(f"[{ts()}] OK   [{handle}] Randomly selected {len(sample)} users to like")

    # Like loop
    liked = 0
    skipped = 0
    errors = 0

    for i, user_did in enumerate(sample):
        # Check for stop request
        if should_stop():
            log(f"[{ts()}] INFO [{handle}] Stop requested. Halting after {liked} likes...")
            break

        # Update progress
        update_progress(i, len(sample))

        # Use stored handle from initial fetch
        user_handle = following.get(user_did, user_did[:20] + "...")

        try:
            l = _like_user_posts(client, user_did, user_handle, likes_per_user, delay_min, delay_max, log_callback, stop_check)
            if l > 0:
                liked += l
                log(f"[{ts()}] OK   [{handle}] [{i+1}/{len(sample)}] Liked {l} posts from @{user_handle}")
            else:
                skipped += 1
        except Exception as e:
            errors += 1
            log(f"[{ts()}] ERR  [{handle}] @{user_handle}: {str(e)[:200]}")

        # Delay between users - interruptible
        if i < len(sample) - 1:
            delay = random.uniform(delay_min, delay_max)
            elapsed = 0
            while elapsed < delay:
                if should_stop():
                    break
                time.sleep(0.5)
                elapsed += 0.5

    return {"handle": handle, "liked": liked, "skipped": skipped, "errors": errors}


def _like_user_posts(client, user_did, user_handle, max_likes, delay_min, delay_max, log_callback=None, stop_check=None):
    """
    Like 1-2 recent posts from a single user.

    Returns:
        int: number of posts liked
    """
    cb = BotCallbacks(log_callback=log_callback, stop_check=stop_check)
    log = cb.log
    should_stop = cb.should_stop

    liked = 0

    try:
        feed = client.app.bsky.feed.get_author_feed({
            "actor": user_did,
            "limit": 5
        })

        if not feed.feed:
            log(f"[{ts()}] SKIP @{user_handle} — no posts")
            return 0

        # Grab extra posts in case some fail, shuffle for randomness
        posts = feed.feed[:max_likes + 2]
        random.shuffle(posts)
        posts = posts[:max_likes]

        for item in posts:
            # Check for stop request
            if should_stop():
                break

            try:
                client.like(item.post.uri, item.post.cid)
                liked += 1
                # Interruptible delay - check for stop every 0.5s
                delay = random.uniform(delay_min, delay_max)
                elapsed = 0
                while elapsed < delay:
                    if should_stop():
                        break
                    time.sleep(0.5)
                    elapsed += 0.5
            except Exception as e:
                err = str(e).lower()
                if "already" in err:
                    pass  # already liked, skip
                else:
                    log(f"[{ts()}] ERR  liking post: {str(e)[:200]}")

    except Exception as e:
        log(f"[{ts()}] ERR  fetching posts for @{user_handle}: {str(e)[:200]}")

    return liked
