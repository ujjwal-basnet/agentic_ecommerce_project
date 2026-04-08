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
    INSTAGRAM,
    VOICE,
    MCP,
    CHANNELS,
    get_channel,
    supports_feature,
    should_send_component,
    can_send_images,
    get_renderer_mode,
    truncate_text,
)

__all__ = [
    "ChannelFeatures",
    "ChannelCapabilities",
    "WEB_APP",
    "WHATSAPP",
    "FB_MESSENGER",
    "INSTAGRAM",
    "VOICE",
    "MCP",
    "CHANNELS",
    "get_channel",
    "supports_feature",
    "should_send_component",
    "can_send_images",
    "get_renderer_mode",
    "truncate_text",
]
