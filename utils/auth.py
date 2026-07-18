"""
Authentication helper for Bluesky accounts.
"""

from atproto import Client


def login(handle: str, password: str) -> Client:
    """
    Login to a Bluesky account.

    Args:
        handle: e.g. "alice.bsky.social"
        password: app password

    Returns:
        Authenticated Client instance

    Raises:
        Exception: if login fails
    """
    client = Client()
    client.login(handle, password)
    return client
