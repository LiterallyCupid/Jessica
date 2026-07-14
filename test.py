from __future__ import annotations
from datetime import datetime

import os

import requests
from dotenv import load_dotenv

import config
from modules.location import get_location

load_dotenv(config.ENV_FILE)

API_KEY = os.getenv("OPENWEATHER_API_KEY")


def _weather():

    # DEBUG CHECK 1: Ensure API Key exists
    if not API_KEY:
        print("❌ DEBUG ERROR: OPENWEATHER_API_KEY is completely missing or empty in your environment variables.")
        return None
    print(f"🔹 API Key found (ends with: ...{API_KEY[-4:] if len(API_KEY) > 4 else '???'})")

    # DEBUG CHECK 2: Ensure location parsing works
    try:
        lat, lon = get_location()
        print(f"🔹 Coordinates retrieved: Lat={lat}, Lon={lon}")
    except Exception as loc_err:
        print(f"❌ DEBUG ERROR: The get_location() function crashed with: {loc_err}")
        return None

    if lat is None or lon is None:
        print("❌ DEBUG ERROR: get_location() completed but returned None for coordinates.")
        return None

    url = "https://api.openweathermap.org/data/2.5/weather"

    params = {
        "lat": lat,
        "lon": lon,
        "appid": API_KEY,
        "units": "metric",
    }

    try:
        print(f"🔹 Sending request to OpenWeather API...")
        response = requests.get(
            url,
            params=params,
            timeout=5,
        )

        # DEBUG CHECK 3: Check HTTP Status (e.g. 401 Unauthorized, 403 Forbidden)
        if response.status_code != 200:
            print(f"❌ DEBUG ERROR: API responded with HTTP Status {response.status_code}")
            print(f"💡 Server Response: {response.text}")
            return None

        return response.json()

    except requests.exceptions.Timeout:
        print("❌ DEBUG ERROR: The request timed out (took longer than 5 seconds).")
        return None
    except requests.exceptions.RequestException as req_err:
        print(f"❌ DEBUG ERROR: A network connection error occurred: {req_err}")
        return None
    except Exception as general_err:
        print(f"❌ DEBUG ERROR: Unexpected error inside _weather(): {general_err}")
        return None


def generate_weather_briefing():

    weather = _weather()

    if weather is None:
        print("❌ DEBUG ERROR: _weather() returned None, briefing generation skipped.")
        return []

    try:
        current = weather["weather"][0]["description"]

        temperature = round(weather["main"]["temp"])

        feels_like = round(weather["main"]["feels_like"])

        humidity = weather["main"]["humidity"]

        wind = weather["wind"]["speed"]

        sunset=datetime.fromtimestamp(weather["sys"]["sunset"]).strftime("%I:%M %p")

        briefing = []
        briefing.append(
            f"It's currently {temperature} degrees with {current}. It feels like {feels_like} degrees."
        )

        if humidity >= 80:
            briefing.append("Humidity is quite high today.")
        elif humidity <= 30:
            briefing.append("The air is fairly dry today.")

        if wind >= 8:
            briefing.append("It's fairly windy outside.")

        if "rain" in current.lower():
            briefing.append("You might want to carry an umbrella.")
        
        hour = datetime.now().hour
        if hour >= 16:
            briefing.append(f"Sunset is at {sunset}.")
        
        return briefing

    except KeyError as key_err:
        print(f"❌ DEBUG ERROR: Parsing failed due to a missing JSON key: {key_err}")
        print(f"💡 Received Payload Sample: {str(weather)[:300]}...")
        return []
    except Exception as parse_err:
        print(f"❌ DEBUG ERROR: Parsing failed: {parse_err}")
        return []

if __name__ == "__main__":
    print("Fetching weather briefing...\n")
    results = generate_weather_briefing()
    
    if results:
        print("\n🎉 SUCCESS! Weather Briefing:")
        for line in results:
            print(f"- {line}")
    else:
        print("\n❌ FAILURE: No briefing could be generated.")
