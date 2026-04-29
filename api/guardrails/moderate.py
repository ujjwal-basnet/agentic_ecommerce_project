"""Moderation hook.

This is intentionally dependency-free for now. Wire provider moderation here
when the policy provider is chosen.
"""

from __future__ import annotations


def moderation_enabled() -> bool:
    return False
