import random
from datetime import datetime

import config
from modules.health import generate_health_briefing

def build_briefing() -> str:
    now = datetime.now()

    current_time = now.strftime("%I:%M %p").lstrip("0")
    day = now.strftime("%A")

    briefing = [
        f"Welcome home sir.",
        f"The time is {current_time} on {day}."
    ]

    briefing.extend(generate_health_briefing())
    briefing.append(random.choice(config.JESSICA_CLOSINGS))

    return " ".join(briefing)