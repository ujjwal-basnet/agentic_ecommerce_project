"""Channels module for multi-channel support.

Provides channel capabilities definitions and adapters for different
communication channels (Web, WhatsApp, Facebook Messenger, Voice, MCP).
"""

from channels.capabilities import (
    ChannelFeatures,
    ChannelCapabilities,
    WEB_APP,
    WHATSAPP,
    FB_MESSENGER,
    VOICE,
    MCP,
    get_channel,
    supports_feature,
    should_send_component,
    truncate_text,
)

__all__ = [
    "ChannelFeatures",
    "ChannelCapabilities",
    "WEB_APP",
    "WHATSAPP",
    "FB_MESSENGER",
    "VOICE",
    "MCP",
    "get_channel",
    "supports_feature",
    "should_send_component",
    "truncate_text",
]
