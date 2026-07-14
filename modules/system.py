import psutil

def _battery():
    battery = psutil.sensors_battery()
    if battery:
        return {
            "percent": battery.percent,
            "plugged_in": battery.power_plugged
        }
    return None

def internet():
    internet=psutil.net_if_stats()
    for interface, stats in internet.items():
        if stats.isup:
            return True
    return False

def generate_system_briefing():
    briefing = []
    battery_info = _battery()
    if battery_info:
        briefing.append(f"Battery is {'plugged in' if battery_info['plugged_in'] else 'not plugged in'}, at {battery_info['percent']}%. ")
    if internet():
        briefing.append("You are connected to the Internet. ")
    return briefing