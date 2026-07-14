from __future__ import annotations
from datetime import datetime

import os
import time

import requests
from dotenv import load_dotenv

import config
from modules.location import get_location

load_dotenv(config.ENV_FILE)

API_KEY = os.getenv("OPENWEATHER_API_KEY")
_CACHE=None
_CACHE_TIME=0
CACHE_DURATION=600


def _weather():
    global _CACHE, _CACHE_TIME

    if not API_KEY:
        return None
    
    now=time.time()

    if _CACHE is not None and (now - _CACHE_TIME) < config.WEATHER_CACHE_SECONDS:
        return _CACHE

    lat, lon = get_location()

    if lat is None or lon is None:
        return None

    url = "https://api.openweathermap.org/data/2.5/weather"

    params = {
        "lat": lat,
        "lon": lon,
        "appid": API_KEY,
        "units": "metric",
    }

    try:

        response = requests.get(
            url,
            params=params,
            timeout=5,
        )

        response.raise_for_status()

        _CACHE = response.json()
        _CACHE_TIME = now

        return _CACHE

    except Exception:

        return None


def generate_weather_briefing():

    weather = _weather()

    if weather is None:
        return []

    current = weather["weather"][0]["description"]

    temperature = round(weather["main"]["temp"])

    feels_like = round(weather["main"]["feels_like"])

    humidity = weather["main"]["humidity"]

    wind = weather["wind"]["speed"]

    sunset=datetime.fromtimestamp(weather["sys"]["sunset"]).strftime("%I:%M %p")

    briefing = []

    briefing.append(
        f"It's currently {temperature} degrees with {current}.It feels like {feels_like} degrees."
    )

    if humidity >= 80:

        briefing.append(
            "Humidity is quite high today."
        )
    elif humidity <= 30:

        briefing.append(
            "The air is fairly dry today."
        )

    if wind >= 8:

        briefing.append(
            "It's fairly windy outside."
        )

    if "rain" in current.lower():

        briefing.append(
            "You might want to carry an umbrella."
        )
    
    hour=datetime.now().hour
    if hour >= 16:
        briefing.append(
            f"Sunset is at {sunset}."
        )
    
    return briefing