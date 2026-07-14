#!/usr/bin/env python3

from __future__ import annotations

import logging
import os
import sys
import threading
import time

import numpy as np
import sounddevice as sd

#--- local imports -----------------------------------------------------------
import config
from modules.speech import get_config
from modules.workspace import wake_jessica
from modules.audio import (
    block_samples, 
    rms_mono, 
    select_input_device
)

# Spotify: "spotify:track:TRACK_ID" or https://open.spotify.com/track/...
# YouTube: https://www.youtube.com/watch?v=...


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("clap_listen")

def main() -> int:
    blocksize = block_samples()
    noise_floor = 1e-4
    last_logged_double = 0.0
    first_clap_time: float | None = None
    spike_armed = True
    is_awake = False

    log.info(
        "Listening (double clap: %.2f–%.2fs apart, rate=%d, block=%d ms, "
        "spike_ratio=%.1f, cooldown=%.2fs). Ctrl+C to stop.",
        config.MIN_DOUBLE_GAP_S,
        config.MAX_DOUBLE_GAP_S,
        config.SAMPLE_RATE,
        config.BLOCK_MS,
        config.SPIKE_RATIO,
        config.COOLDOWN_S,
    )
    if config.OPEN_CHATGPT:
        chatgpt_url = (os.environ.get("CHATGPT_URL") or "https://chatgpt.com").strip()
        log.info(
            "After Spotify, open ChatGPT in Brave%s on monitor %d: %s",
            " fullscreen" if config.OPEN_BRAVE_FULLSCREEN else "",
            config.CHATGPT_BRAVE_MONITOR,
            chatgpt_url,
        )
    if config.OPEN_TRADINGVIEW:
        tradingview_url = (
            os.environ.get("TRADINGVIEW_URL")
            or "https://in.tradingview.com/chart/GmjweavQ/?symbol=NSE%3ANIFTY"
        ).strip()
        log.info(
            "After Spotify, open TradingView in Brave%s on monitor %d: %s",
            " fullscreen" if config.OPEN_BRAVE_FULLSCREEN else "",
            config.TRADINGVIEW_BRAVE_MONITOR,
            tradingview_url,
        )
    if config.WELCOME_ENABLED:
        ev, em, ef, er = get_config()
        log.info(
            "After song + %.2fs: (ElevenLabs voice=%s, model=%s, format=%s, pcm_rate=%d)",
            config.AFTER_SONG_DELAY_S,
            ev or "(unset)",
            em,
            ef,
            er,
        )
    
    input_idx=select_input_device(blocksize)

    try:
        with sd.InputStream(
            device=input_idx,
            samplerate=config.SAMPLE_RATE,
            channels=config.CHANNELS,
            dtype="float32",
            blocksize=blocksize,
        ) as stream:
            while True:
                data, overflowed = stream.read(blocksize)
                if overflowed:
                    log.warning("Input overflow; try a larger BLOCK_MS")

                level = rms_mono(data)
                peak = float(np.max(np.abs(data)))

                quiet_gate = noise_floor * config.QUIET_GATE_MULT
                if level < quiet_gate:
                    noise_floor = config.NOISE_FLOOR_ALPHA * noise_floor + (
                        1.0 - config.NOISE_FLOOR_ALPHA
                    ) * level
                    noise_floor = max(noise_floor, 1e-7)

                threshold = max(noise_floor * config.SPIKE_RATIO, config.MIN_RMS)
                now = time.monotonic()
                retrigger_level = threshold * config.RETRIGGER_RATIO

                if level < retrigger_level:
                    spike_armed = True

                if (
                    spike_armed
                    and level >= threshold
                    and (now - last_logged_double) >= config.COOLDOWN_S
                ):
                    spike_armed = False
                    if first_clap_time is None:
                        first_clap_time = now
                    else:
                        gap = now - first_clap_time
                        if gap < config.MIN_DOUBLE_GAP_S:
                            pass
                        elif gap <= config.MAX_DOUBLE_GAP_S:
                            first_clap_time = None
                            last_logged_double = now
                            if not is_awake:
                                is_awake = True
                                log.info(
                                    "Double clap detected (gap=%.3fs, rms=%.5f, peak=%.5f, noise_floor=%.5f, threshold=%.5f) — running welcome once",
                                    gap,
                                    level,
                                    peak,
                                    noise_floor,
                                    threshold,
                                )
                                threading.Thread(
                                    target=wake_jessica,
                                    daemon=True
                                ).start()
                        else:
                            first_clap_time = now

    except KeyboardInterrupt:
        log.info("Stopped.")
        return 0
    except sd.PortAudioError as e:
        log.error("Audio error: %s", e)
        log.error("If PortAudio fails, install/repair drivers or try another SAMPLE_RATE.")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
