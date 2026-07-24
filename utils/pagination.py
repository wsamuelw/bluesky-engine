"""
Shared pagination utilities for Bluesky API calls.
"""

from utils.constants import API_LIMIT


def paginate_follows(client, actor):
    """Paginate through follows. Returns list of user objects."""
    results = []
    cursor = None
    while True:
        params = {"actor": actor, "limit": API_LIMIT}
        if cursor:
            params["cursor"] = cursor
        result = client.app.bsky.graph.get_follows(params)
        results.extend(result.follows)
        cursor = result.cursor
        if not cursor:
            break
    return results


def paginate_followers(client, actor):
    """Paginate through followers. Returns list of user objects."""
    results = []
    cursor = None
    while True:
        params = {"actor": actor, "limit": API_LIMIT}
        if cursor:
            params["cursor"] = cursor
        result = client.app.bsky.graph.get_followers(params)
        results.extend(result.followers)
        cursor = result.cursor
        if not cursor:
            break
    return results


def paginate_records(client, repo, collection):
    """Paginate through repo records. Returns list of record objects."""
    results = []
    cursor = None
    while True:
        params = {"repo": repo, "collection": collection, "limit": API_LIMIT}
        if cursor:
            params["cursor"] = cursor
        result = client.com.atproto.repo.list_records(params)
        results.extend(result.records)
        cursor = result.cursor
        if not cursor:
            break
    return results
