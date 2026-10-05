"""Errors whose message is written for the user and safe to show as-is."""


class FriendlyError(Exception):
    """Raise (or subclass) this when the message should be shown directly in the UI."""
