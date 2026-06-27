from __future__ import annotations

import logging
import os

import numpy as np
import sounddevice as sd
from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs

import config

log = logging.getLogger(__name__)

load_dotenv(config.ENV_FILE)

api_key = (os.environ.get("ELEVENLABS_API_KEY") or "").strip()

client = ElevenLabs(api_key=api_key)


def _pcm_sample_rate(output_format: str) -> int:
    override = (os.environ.get("ELEVENLABS_PCM_SAMPLE_RATE") or "").strip()

    if override.isdigit():
        return int(override)

    if output_format.startswith("pcm_"):
        try:
            return int(output_format.split("_", 1)[1])
        except Exception:
            pass

    return config.DEFAULT_PCM_RATE


def get_config():

    voice = (os.environ.get("ELEVENLABS_VOICE_ID") or "").strip()

    model = (
        os.environ.get("ELEVENLABS_MODEL_ID")
        or config.DEFAULT_MODEL
    ).strip()

    fmt = (
        os.environ.get("ELEVENLABS_OUTPUT_FORMAT")
        or config.DEFAULT_OUTPUT_FORMAT
    ).strip()

    return voice, model, fmt, _pcm_sample_rate(fmt)


def speak(text: str):

    voice, model, fmt, sample_rate = get_config()

    try:

        audio = client.text_to_speech.convert(
            voice_id=voice,
            model_id=model,
            output_format=fmt,
            text=text,
        )

        pcm = b"".join(audio)

        if not pcm:
            log.warning("ElevenLabs returned empty audio.")
            return

        samples = (
            np.frombuffer(pcm, dtype=np.int16)
            .astype(np.float32)
            / 32768.0
        )

        sd.play(samples, sample_rate)
        sd.wait()

    except Exception as e:
        log.warning("ElevenLabs failed: %s", e)