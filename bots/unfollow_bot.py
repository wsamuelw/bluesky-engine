"""
Unfollow Bot — unfollows non-followers older than X days.

Uses synchronous atproto client for Streamlit compatibility.
Passes a callback function for live log updates.
"""

import random
import time
from datetime import datetime, timedelta, timezone
from utils.pagination import paginate_follows, paginate_followers, paginate_records
from utils.constants import INTERRUPT_TICK, RATE_LIMIT_PAUSE
from core.callbacks import BotCallbacks

from atproto import Client


def ts() -> str:
    """Current timestamp for log output."""
    return datetime.now().strftime("%H:%M:%S")


def unfollow_bot_run(accounts, days_threshold, daily_cap, delay_min, delay_max, exemptions, log_callback=None, stop_check=None, progress_callback=None):
    """
    Run unfollow bot on all enabled accounts.

    Args:
        accounts: list of account dicts with handle, password, enabled
        days_threshold: only unfollow if followed more than X days ago
        daily_cap: max unfollows per account per run
        delay_min: min seconds between unfollows
        delay_max: max seconds between unfollows
        exemptions: list of handles to never unfollow
        log_callback: function to call with each log line
        stop_check: function that returns True if bot should stop
        progress_callback: function to call with (completed, total) for progress tracking

    Returns:
        list of result dicts
    """
    cb = BotCallbacks(log_callback=log_callback, stop_check=stop_check, progress_callback=progress_callback)
    log = cb.log
    should_stop = cb.should_stop
    update_progress = cb.update_progress

    enabled = [a for a in accounts if a.get("enabled", True)]

    results = []

    for acc in enabled:
        if should_stop():
            log("Stop requested. Halting...")
            break
        result = _run_single_account(acc, days_threshold, daily_cap, delay_min, delay_max, exemptions, log_callback, stop_check, progress_callback)
        results.append(result)

    # Summary
    log("")
    log("=" * 55)
    log("COMPLETE")
    log("=" * 55)

    total_unfollowed = 0
    total_skipped = 0
    total_errors = 0

    for r in results:
        log(f"  @{r['handle']}: {r['unfollowed']} unfollowed, {r['skipped']} skipped, {r['errors']} errors")
        total_unfollowed += r["unfollowed"]
        total_skipped += r["skipped"]
        total_errors += r["errors"]

    log("")
    log(f"  TOTAL: {total_unfollowed} unfollowed, {total_skipped} skipped, {total_errors} errors")
    log(f"  Finished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    return results


def _run_single_account(account, days_threshold, daily_cap, delay_min, delay_max, exemptions, log_callback=None, stop_check=None, progress_callback=None):
    """
    Run unfollow bot for a single account.

    Returns:
        dict with handle, unfollowed, skipped, errors
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
            profile = client.login(handle, password)
            log(f"[{ts()}] OK   [{handle}] Authenticated")
        except Exception as e:
            log(f"[{ts()}] ERR  [{handle}] Auth failed: {e}")
            return {"handle": handle, "unfollowed": 0, "skipped": 0, "errors": 1}
    else:
        profile = client.app.bsky.actor.get_profile({"actor": handle})
        log(f"[{ts()}] OK   [{handle}] Using cached client")

    # Build DID → handle map for logging (avoids per-user API calls)
    log(f"[{ts()}] INFO [{handle}] Building handle map...")
    handle_map = {user.did: user.handle for user in paginate_follows(client, handle)}
    log(f"[{ts()}] OK   [{handle}] Mapped {len(handle_map)} handles")

    # Pull who you follow (with dates from repo records)
    log(f"[{ts()}] INFO [{handle}] Pulling following list with dates...")
    records = paginate_records(client, profile.did, "app.bsky.graph.follow")
    following_records = []
    for record in records:
        subject = record.value.subject if hasattr(record.value, 'subject') else ""
        created_at = record.value.created_at if hasattr(record.value, 'created_at') else ""
        following_records.append({
            "did": subject,
            "uri": record.uri,
            "created_at": created_at,
        })
    log(f"[{ts()}] OK   [{handle}] Following {len(following_records)} accounts")

    # Pull your followers
    log(f"[{ts()}] INFO [{handle}] Pulling followers list...")
    follower_users = paginate_followers(client, handle)
    followers = set(user.did for user in follower_users)
    log(f"[{ts()}] OK   [{handle}] {len(followers)} followers")

    # Find non-followers
    non_followers = [r for r in following_records if r["did"] not in followers]
    log(f"[{ts()}] OK   [{handle}] {len(non_followers)} non-followers")

    # Filter by date threshold
    cutoff = datetime.now(timezone.utc) - timedelta(days=days_threshold)
    eligible = []

    for record in non_followers:
        try:
            created = datetime.fromisoformat(record["created_at"].replace("Z", "+00:00"))
            if created < cutoff:
                eligible.append(record)
        except Exception:
            # If date parsing fails, include it
            eligible.append(record)

    log(f"[{ts()}] OK   [{handle}] {len(eligible)} eligible (>{days_threshold} days old)")

    # Apply exemptions
    if exemptions:
        exempt_set = set(e.lower().strip() for e in exemptions if e.strip())
        # We need to resolve handles for exemption check
        # For now, we'll check handles during the unfollow loop
        log(f"[{ts()}] INFO [{handle}] {len(exempt_set)} exemptions configured")

    if not eligible:
        log(f"[{ts()}] WARN [{handle}] No eligible accounts to unfollow. Skipping.")
        return {"handle": handle, "unfollowed": 0, "skipped": 0, "errors": 0}

    # Cap at daily limit
    to_unfollow = eligible[:daily_cap]
    log(f"[{ts()}] OK   [{handle}] Will unfollow {len(to_unfollow)} accounts (cap: {daily_cap})")

    # Unfollow loop
    unfollowed = 0
    skipped = 0
    errors = 0
    exemption_set = set(e.lower().strip() for e in exemptions if e.strip()) if exemptions else set()

    for i, record in enumerate(to_unfollow):
        # Check for stop request
        if should_stop():
            log(f"[{ts()}] INFO [{handle}] Stop requested. Halting after {unfollowed} unfollows...")
            break

        # Update progress
        update_progress(i, len(to_unfollow))

        did = record["did"]

        # Use stored handle from initial fetch
        user_handle = handle_map.get(did, did[:20] + "...")

        # Check exemptions
        if exemption_set and user_handle.lower() in exemption_set:
            log(f"[{ts()}] SKIP [{handle}] @{user_handle} — exempt")
            skipped += 1
            continue

        try:
            client.delete_follow(record["uri"])
            unfollowed += 1
            log(f"[{ts()}] OK   [{handle}] [{unfollowed}/{len(to_unfollow)}] Unfollowed @{user_handle}")
        except Exception as e:
            errors += 1
            log(f"[{ts()}] ERR  [{handle}] @{user_handle}: {str(e)[:200]}")
            if "rate" in str(e).lower() or "429" in str(e):
                log(f"[{ts()}] WARN [{handle}] Rate limited. Pausing 60s...")
                time.sleep(RATE_LIMIT_PAUSE)

        # Delay between unfollows - interruptible
        if i < len(to_unfollow) - 1:
            delay = random.uniform(delay_min, delay_max)
            elapsed = 0
            while elapsed < delay:
                if should_stop():
                    break
                time.sleep(INTERRUPT_TICK)
                elapsed += 0.5

    return {"handle": handle, "unfollowed": unfollowed, "skipped": skipped, "errors": errors}


def get_unfollow_preview(accounts, days_threshold, exemptions, log_callback=None):
    """
    Preview who will be unfollowed (without actually unfollowing).

    Returns:
        list of dicts with handle, eligible_count, total_non_followers
    """
    cb = BotCallbacks(log_callback=log_callback)
    log = cb.log

    results = []

    for acc in accounts:
        if not acc.get("enabled") or not acc.get("handle") or not acc.get("password"):
            continue

        handle = acc["handle"]
        password = acc["password"]

        try:
            client = Client()
            profile = client.login(handle, password)

            # Pull following with dates
            records = paginate_records(client, profile.did, "app.bsky.graph.follow")
            following_records = []
            for record in records:
                subject = record.value.subject if hasattr(record.value, 'subject') else ""
                created_at = record.value.created_at if hasattr(record.value, 'created_at') else ""
                following_records.append({
                    "did": subject,
                    "created_at": created_at,
                })

            # Pull followers
            followers = set(user.did for user in paginate_followers(client, handle))

            # Find non-followers
            non_followers = [r for r in following_records if r["did"] not in followers]

            # Filter by date
            cutoff = datetime.now(timezone.utc) - timedelta(days=days_threshold)
            eligible = []
            for record in non_followers:
                try:
                    created = datetime.fromisoformat(record["created_at"].replace("Z", "+00:00"))
                    if created < cutoff:
                        eligible.append(record)
                except Exception:
                    eligible.append(record)

            results.append({
                "handle": handle,
                "total_following": len(following_records),
                "total_followers": len(followers),
                "non_followers": len(non_followers),
                "eligible": len(eligible),
            })

        except Exception as e:
            results.append({
                "handle": handle,
                "error": str(e)[:80],
            })

    return results
