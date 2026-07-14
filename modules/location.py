from __future__ import annotations
from winsdk.windows.devices.geolocation import Geolocator
import asyncio

async def _get_location():

    from winsdk.windows.devices.geolocation import Geolocator

    locator = Geolocator()

    position = await locator.get_geoposition_async()

    latitude = position.coordinate.point.position.latitude
    longitude = position.coordinate.point.position.longitude

    return latitude, longitude


def get_location():

    try:
        return asyncio.run(_get_location())

    except Exception:

        return None, None