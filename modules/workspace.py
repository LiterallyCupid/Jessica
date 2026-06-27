from __future__ import annotations

import logging
import subprocess
import threading

import config
from modules.browser import open_chatgpt, open_tradingview
from modules.briefing import build_briefing
from modules.speech import speak

log = logging.getLogger(__name__)


def play_song() -> None:
    try:
        subprocess.Popen(
            [config.AIMP_EXE, config.TRACK_PATH],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError as e:
        log.warning("Could not launch AIMP: %s", e)


def wake_jessica() -> None:
    """
    Jessica's wake-up sequence.
    """

    for task in (open_chatgpt, open_tradingview):
        threading.Thread(target=task, daemon=True).start()

    speak(build_briefing())

    play_song()