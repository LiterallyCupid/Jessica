import random
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

import config
#from modules.health import generate_health_briefing
from modules.system import generate_system_briefing,_battery
from modules.weather import generate_weather_briefing

def build_briefing() -> str:
    now = datetime.now()

    current_time = now.strftime("%I:%M %p").lstrip("0")
    day = now.strftime("%A")

    hour = now.hour
    if hour<12:
        greeting = random.choice(config.MORNING_GREETINGS)
    elif hour<17:
        greeting = random.choice(config.AFTERNOON_GREETINGS)
    elif hour<21:
        greeting = random.choice(config.EVENING_GREETINGS)
    else:
        greeting = random.choice(config.NIGHT_GREETINGS)
    
    battery=_battery()
    if battery and battery['percent']<20 and not battery['plugged_in']:
        greeting += " Your battery is running low."

    briefing=[
        greeting,
        f"The time is {current_time} on {day}.",
    ]

    #briefing.extend(generate_health_briefing())
    with ThreadPoolExecutor(max_workers=2) as executor:
        weather_future = executor.submit(generate_weather_briefing)
        system_future = executor.submit(generate_system_briefing)
        briefing.extend(weather_future.result())
        briefing.extend(system_future.result())

    briefing.append(" ")    
    briefing.append(random.choice(config.JESSICA_CLOSINGS))

    return " ".join(briefing)