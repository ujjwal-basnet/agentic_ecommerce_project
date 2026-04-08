"""WeatherAgent — weather info via OpenWeatherMap. Sets _last_tool = 'get_weather'."""

import random
import requests
from custom_mcp import create_mcp_message
import config
from channels.capabilities import (
    ChannelCapabilities,
    ChannelFeatures,
    WEB_APP,
    truncate_text,
    should_send_component,
)


class WeatherAgent:
    def __init__(self):
        self._last_tool = None

    def handle(self, msg: dict, channel_caps: ChannelCapabilities = None, **kw) -> dict:
        if channel_caps is None:
            channel_caps = WEB_APP

        content = msg.get("content", {})
        location = content.get("location", "Kathmandu")
        self._last_tool = "get_weather"

        try:
            if config.OPENWEATHER_API_KEY:
                data = self._fetch_real(location)
            else:
                data = self._mock(location)

            return self._format_for_channel(data, channel_caps)

        except Exception as e:
            return create_mcp_message("WeatherAgent", {
                "status": "error",
                "tool": self._last_tool,
                "error": str(e),
                "text": f"Could not fetch weather for {location}.",
                "component": None,
            })

    def _format_for_channel(self, data: dict, caps: ChannelCapabilities) -> dict:
        """Format weather response based on channel capabilities."""
        loc = data["location"]
        temp = data["temperature"]
        weather = data["weather"]
        feels = data.get("feels_like", temp)
        humidity = data.get("humidity", "")

        base = {
            "status": "ok",
            "tool": self._last_tool,
            **data,
        }

        # VOICE: short speakable text + SSML
        if ChannelFeatures.VOICE_OUTPUT in caps.features:
            text = f"It's {weather} in {loc}, {temp} degrees."
            base["text"] = truncate_text(text, caps)
            base["ssml"] = (
                f"<speak>It's {weather} in {loc}, "
                f"<say-as interpret-as='cardinal'>{int(temp)}</say-as> degrees celsius, "
                f"feels like <say-as interpret-as='cardinal'>{int(feels)}</say-as>.</speak>"
            )
            base["component"] = None
            return create_mcp_message("WeatherAgent", base)

        # WEB: React component
        if should_send_component(caps):
            base["text"] = f"Weather in {loc}: {weather}, {temp}°C."
            base["component"] = "WeatherCard"
            return create_mcp_message("WeatherAgent", base)

        # WHATSAPP / FB / MCP: plain text
        text = (
            f"Weather in {loc}: {weather}\n"
            f"Temperature: {temp}°C (feels like {feels}°C)\n"
            f"Humidity: {humidity}%"
        )
        base["text"] = truncate_text(text, caps)
        base["component"] = None
        return create_mcp_message("WeatherAgent", base)

    def _fetch_real(self, location: str) -> dict:
        url = "https://api.openweathermap.org/data/2.5/weather"
        resp = requests.get(url, params={
            "q": location, "appid": config.OPENWEATHER_API_KEY,
            "units": "metric",
        }, timeout=10)
        resp.raise_for_status()
        d = resp.json()
        return {
            "location": d.get("name", location),
            "temperature": round(d["main"]["temp"], 1),
            "feels_like": round(d["main"]["feels_like"], 1),
            "humidity": d["main"]["humidity"],
            "wind_speed": round(d.get("wind", {}).get("speed", 0), 1),
            "weather": d["weather"][0]["description"].title() if d.get("weather") else "Clear",
            "icon": d["weather"][0].get("icon", "01d") if d.get("weather") else "01d",
        }

    def _mock(self, location: str) -> dict:
        conditions = ["Sunny", "Partly Cloudy", "Cloudy", "Light Rain", "Clear Sky"]
        icons = ["01d", "02d", "03d", "10d", "01d"]
        idx = random.randint(0, len(conditions) - 1)
        temp = round(random.uniform(15, 35), 1)
        return {
            "location": location,
            "temperature": temp,
            "feels_like": round(temp + random.uniform(-2, 2), 1),
            "humidity": random.randint(30, 90),
            "wind_speed": round(random.uniform(1, 15), 1),
            "weather": conditions[idx],
            "icon": icons[idx],
        }
