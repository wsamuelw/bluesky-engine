"""
Unfollow Bot — unfollows non-followers older than X days.

Uses synchronous atproto client for Streamlit compatibility.
Passes a callback function for live log updates.
"""

import random
import time
from datetime import datetime, timedelta, timezone

from atproto import Client


def ts() -> str:
    """Current timestamp for log output."""
    return datetime.now().strftime("%H:%M:%S")


def unfollow_bot_run(accounts, days_threshold, daily_cap, delay_min, delay_max, exemptions, log_callback=None):
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

    Returns:
        list of result dicts
    """
    def log(line):
        if log_callback:
            log_callback(line)

    enabled = [a for a in accounts if a.get("enabled", True)]

    log("=" * 55)
    log(f"STARTING UNFOLLOW BOT — {len(enabled)} ACCOUNTS")
    log("=" * 55)

    results = []

    for acc in enabled:
        result = _run_single_account(acc, days_threshold, daily_cap, delay_min, delay_max, exemptions, log_callback)
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


def _run_single_account(account, days_threshold, daily_cap, delay_min, delay_max, exemptions, log_callback=None):
    """
    Run unfollow bot for a single account.

    Returns:
        dict with handle, unfollowed, skipped, errors
    """
    def log(line):
        if log_callback:
            log_callback(line)

    handle = account["handle"]
    password = account["password"]

    # Login
    try:
        client = Client()
        profile = client.login(handle, password)
        log(f"[{ts()}] OK   [{handle}] Authenticated")
    except Exception as e:
        log(f"[{ts()}] ERR  [{handle}] Auth failed: {e}")
        return {"handle": handle, "unfollowed": 0, "skipped": 0, "errors": 1}

    # Pull who you follow (with dates from repo records)
    log(f"[{ts()}] INFO [{handle}] Pulling following list with dates...")

    following_records = []
    cursor = None

    while True:
        params = {
            "repo": profile.did,
            "collection": "app.bsky.graph.follow",
            "limit": 100,
        }
        if cursor:
            params["cursor"] = cursor

        result = client.com.atproto.repo.list_records(params)

        for record in result.records:
            subject = record.value.get("subject", "")
            created_at = record.value.get("createdAt", "")
            following_records.append({
                "did": subject,
                "uri": record.uri,
                "created_at": created_at,
            })

        cursor = result.cursor
        if not cursor:
            break

    log(f"[{ts()}] OK   [{handle}] Following {len(following_records)} accounts")

    # Pull your followers
    log(f"[{ts()}] INFO [{handle}] Pulling followers list...")
    followers = set()
    cursor = None
    while True:
        params = {"actor": handle, "limit": 100}
        if cursor:
            params["cursor"] = cursor
        result = client.app.bsky.graph.get_followers(params)
        for user in result.followers:
            followers.add(user.did)
        cursor = result.cursor
        if not cursor:
            break
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
        except:
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

    for i, record in enumerate(to_unfollow):
        did = record["did"]

        # Get handle for logging and exemption check
        try:
            profile_info = client.app.bsky.actor.get_profile({"actor": did})
            user_handle = profile_info.handle
        except:
            user_handle = did[:20] + "..."

        # Check exemptions
        if exemptions and user_handle.lower() in set(e.lower().strip() for e in exemptions if e.strip()):
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
                time.sleep(60)

        # Delay between unfollows
        if i < len(to_unfollow) - 1:
            delay = random.uniform(delay_min, delay_max)
            time.sleep(delay)

    return {"handle": handle, "unfollowed": unfollowed, "skipped": skipped, "errors": errors}


def get_unfollow_preview(accounts, days_threshold, exemptions, log_callback=None):
    """
    Preview who will be unfollowed (without actually unfollowing).

    Returns:
        list of dicts with handle, eligible_count, total_non_followers
    """
    def log(line):
        if log_callback:
            log_callback(line)

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
            following_records = []
            cursor = None
            while True:
                params = {
                    "repo": profile.did,
                    "collection": "app.bsky.graph.follow",
                    "limit": 100,
                }
                if cursor:
                    params["cursor"] = cursor
                result = client.com.atproto.repo.list_records(params)
                for record in result.records:
                    following_records.append({
                        "did": record.value.get("subject", ""),
                        "created_at": record.value.get("createdAt", ""),
                    })
                cursor = result.cursor
                if not cursor:
                    break

            # Pull followers
            followers = set()
            cursor = None
            while True:
                params = {"actor": handle, "limit": 100}
                if cursor:
                    params["cursor"] = cursor
                result = client.app.bsky.graph.get_followers(params)
                for user in result.followers:
                    followers.add(user.did)
                cursor = result.cursor
                if not cursor:
                    break

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
                except:
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
