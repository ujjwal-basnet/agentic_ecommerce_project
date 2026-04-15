"""Channel capabilities model for multi-channel support.

Defines what each channel (Web, WhatsApp, FB Messenger, Voice, MCP) can display,
and provides utilities for formatting responses appropriately.
"""

from enum import Flag, auto
from dataclasses import dataclass


class ChannelFeatures(Flag):
    """Feature flags for channel capabilities."""
    TEXT = auto()           # Can display text
    IMAGES = auto()         # Can show images (URLs)
    CAROUSEL = auto()       # Can show multiple items in carousel
    BUTTONS = auto()        # Can show clickable buttons
    QUICK_REPLIES = auto()  # Can show quick reply buttons
    VOICE_OUTPUT = auto()   # Is voice-only (text-to-speech)
    RICH_UI = auto()        # Can render React/Vue components
    MARKDOWN = auto()       # Supports markdown formatting


@dataclass(frozen=True)
class ChannelCapabilities:
    """Defines what a channel can do and its constraints."""
    name: str
    features: ChannelFeatures
    max_text_length: int      # Character limit for messages
    max_carousel_items: int   # Max items in a list/carousel
    max_buttons: int          # Max buttons per item
    supports_ssml: bool       # Needs SSML for voice


# Pre-defined channel types
WEB_APP = ChannelCapabilities(
    name="web",
    features=ChannelFeatures.TEXT | ChannelFeatures.IMAGES | 
               ChannelFeatures.BUTTONS | ChannelFeatures.CAROUSEL | 
               ChannelFeatures.RICH_UI | ChannelFeatures.MARKDOWN,
    max_text_length=10000,
    max_carousel_items=50,
    max_buttons=10,
    supports_ssml=False,
)

WHATSAPP = ChannelCapabilities(
    name="whatsapp",
    features=ChannelFeatures.TEXT | ChannelFeatures.IMAGES | 
               ChannelFeatures.BUTTONS | ChannelFeatures.QUICK_REPLIES,
    max_text_length=4096,
    max_carousel_items=10,  # WhatsApp interactive list limit
    max_buttons=3,
    supports_ssml=False,
)

FB_MESSENGER = ChannelCapabilities(
    name="facebook",
    features=ChannelFeatures.TEXT | ChannelFeatures.IMAGES | 
               ChannelFeatures.CAROUSEL | ChannelFeatures.BUTTONS | 
               ChannelFeatures.QUICK_REPLIES,
    max_text_length=2000,
    max_carousel_items=10,  # Generic template limit
    max_buttons=3,
    supports_ssml=False,
)

VOICE = ChannelCapabilities(
    name="voice",
    features=ChannelFeatures.TEXT | ChannelFeatures.VOICE_OUTPUT,
    max_text_length=500,    # Short for TTS
    max_carousel_items=5,   # "Say 1, 2, 3, 4, or 5"
    max_buttons=0,
    supports_ssml=True,     # Need SSML for natural speech
)

MCP = ChannelCapabilities(
    name="mcp",
    features=ChannelFeatures.TEXT | ChannelFeatures.MARKDOWN,  # MCP is text-only by spec
    max_text_length=10000,
    max_carousel_items=50,
    max_buttons=0,
    supports_ssml=False,
)

INSTAGRAM = ChannelCapabilities(
    name="instagram",
    features=ChannelFeatures.TEXT | ChannelFeatures.IMAGES |
               ChannelFeatures.BUTTONS | ChannelFeatures.QUICK_REPLIES,
    max_text_length=1000,
    max_carousel_items=10,
    max_buttons=3,
    supports_ssml=False,
)


# Channel lookup by name
CHANNELS = {
    "web": WEB_APP,
    "whatsapp": WHATSAPP,
    "facebook": FB_MESSENGER,
    "instagram": INSTAGRAM,
    "voice": VOICE,
    "mcp": MCP,
}


def get_channel(name: str) -> ChannelCapabilities:
    """Get channel capabilities by name.
    
    Args:
        name: Channel name (web, whatsapp, facebook, voice, mcp)
        
    Returns:
        ChannelCapabilities for the named channel
        
    Raises:
        ValueError: If channel name is unknown
    """
    if name not in CHANNELS:
        raise ValueError(f"Unknown channel: {name}. Available: {list(CHANNELS.keys())}")
    return CHANNELS[name]


def supports_feature(caps: ChannelCapabilities, feature: ChannelFeatures) -> bool:
    """Check if channel supports a specific feature.
    
    Args:
        caps: Channel capabilities
        feature: Feature to check
        
    Returns:
        True if channel supports the feature
    """
    return feature in caps.features


def should_send_component(caps: ChannelCapabilities) -> bool:
    """Check if channel can receive UI components.
    
    Args:
        caps: Channel capabilities
        
    Returns:
        True if channel supports RICH_UI components
    """
    return ChannelFeatures.RICH_UI in caps.features


def can_send_images(caps: ChannelCapabilities) -> bool:
    """Check if channel can display images."""
    return ChannelFeatures.IMAGES in caps.features


def get_renderer_mode(caps: ChannelCapabilities) -> str:
    """Derive renderer mode string from channel capabilities.

    Returns:
        "web" for rich UI channels, "messaging" for image-capable text channels,
        "text" for text-only channels.
    """
    if ChannelFeatures.RICH_UI in caps.features:
        return "web"
    if ChannelFeatures.IMAGES in caps.features:
        return "messaging"
    return "text"


def truncate_text(text: str, caps: ChannelCapabilities) -> str:
    """Truncate text to channel's max length.
    
    Args:
        text: Text to potentially truncate
        caps: Channel capabilities with max_text_length
        
    Returns:
        Truncated text with "..." if needed
    """
    if len(text) <= caps.max_text_length:
        return text
    return text[:caps.max_text_length - 3] + "..."
