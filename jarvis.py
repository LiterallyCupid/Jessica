#!/usr/bin/env python3

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import webbrowser
import random
from pathlib import Path
from datetime import datetime
from elevenlabs.client import ElevenLabs

from dotenv import load_dotenv
import numpy as np
import sounddevice as sd

#--- local imports -----------------------------------------------------------
from modules.health import generate_health_briefing
from modules.memory import load_memory


# --- tuning knobs -----------------------------------------------------------
SAMPLE_RATE = 44100
BLOCK_MS = 40
CHANNELS = 1

SPIKE_RATIO = 7.0
COOLDOWN_S = 0.45
MIN_DOUBLE_GAP_S = 0.05
MAX_DOUBLE_GAP_S = 0.35
RETRIGGER_RATIO = 0.55
NOISE_FLOOR_ALPHA = 0.992
MIN_RMS = 0.012
QUIET_GATE_MULT = 2.2  # update noise floor only when below floor * this

# Spotify: "spotify:track:TRACK_ID" or https://open.spotify.com/track/...
# YouTube: https://www.youtube.com/watch?v=...
AIMP_EXE = r"C:\Program Files\AIMP\AIMP.exe"
TRACK_PATH=r"C:\Music\OST\Ala Vaikunthapurramuloo - OST (2023)\02. Thaman S - Bantu Intro.flac"

# Google Chrome (fallback: default browser). URLs overridable in .env.
OPEN_CHATGPT = True
OPEN_TRADINGVIEW = True
OPEN_BRAVE_FULLSCREEN = True
# False = default Brave profile (your normal user, extensions, cookies). True = temp dirs under %TEMP% per site.
BRAVE_SEPARATE_SITE_PROFILES = False
# Which physical screen (1 = leftmost/top-first after sorting). Windows only; ignored elsewhere.
CHATGPT_BRAVE_MONITOR = 1
TRADINGVIEW_BRAVE_MONITOR = 2
JESSICA_CLOSINGS = [
    "Ready when you are.",
    "All systems are operational.",
    "Your workspace is prepared.",
    "I've got everything ready.",
    "Let's build something today."
]

def build_briefing() -> str:
    now = datetime.now()

    current_time = now.strftime("%I:%M %p").lstrip("0")
    day = now.strftime("%A")

    memory = load_memory()

    parts = [
        f"Welcome home sir.",
        f"The time is {current_time} on {day}."
    ]

    parts.extend(generate_health_briefing(memory))
    parts.append(random.choice(JESSICA_CLOSINGS))

    return " ".join(parts)


WELCOME_ENABLED = True
AFTER_SONG_DELAY_S = 1.0
# Save ElevenLabs PCM as WAV under .cache/jarvis_welcome/; replay skips the API when the key matches.
WELCOME_CACHE_ENABLED = False

load_dotenv(Path(__file__).resolve().parent / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("clap_listen")

def block_samples() -> int:
    n = int(SAMPLE_RATE * BLOCK_MS / 1000)
    return max(n, 1)


def rms_mono(block: np.ndarray) -> float:
    if block.ndim > 1:
        block = np.mean(block.astype(np.float64), axis=1)
    else:
        block = block.astype(np.float64)
    if block.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(block**2)))


def _elevenlabs_pcm_sample_rate(output_format: str) -> int:
    override = (os.environ.get("ELEVENLABS_PCM_SAMPLE_RATE") or "").strip()
    if override.isdigit():
        return int(override)
    if output_format.startswith("pcm_"):
        try:
            return int(output_format.split("_", maxsplit=1)[1])
        except (ValueError, IndexError):
            pass
    return 24000


def elevenlabs_env_config() -> tuple[str, str, str, int]:
    """voice_id, model_id, output_format, pcm_sample_rate."""
    voice = (os.environ.get("ELEVENLABS_VOICE_ID") or "").strip()
    model = (os.environ.get("ELEVENLABS_MODEL_ID") or "eleven_multilingual_v2").strip()
    fmt = (os.environ.get("ELEVENLABS_OUTPUT_FORMAT") or "pcm_24000").strip()
    rate = _elevenlabs_pcm_sample_rate(fmt)
    return voice, model, fmt, rate

def say_welcome():
    api_key = (os.environ.get("ELEVENLABS_API_KEY") or "").strip()

    if not api_key:
        log.warning("ELEVENLABS_API_KEY not found in .env")
        return

    voice_id = (
        os.environ.get("ELEVENLABS_VOICE_ID")
        or "cgSgspJ2msm6clMCkdW9"  # Jessica fallback
    ).strip()

    try:
        client = ElevenLabs(api_key=api_key)

        audio = client.text_to_speech.convert(
            voice_id=voice_id,
            model_id="eleven_multilingual_v2",
            output_format="pcm_24000",
            text=build_briefing(),
        )

        pcm_bytes = b"".join(audio)

        if not pcm_bytes:
            log.warning("ElevenLabs returned empty audio.")
            return

        pcm_i16 = np.frombuffer(pcm_bytes, dtype=np.int16)
        pcm_f32 = pcm_i16.astype(np.float32) / 32768.0

        _, _, _, sample_rate = elevenlabs_env_config()

        sd.play(pcm_f32, sample_rate)
        sd.wait()

    except Exception as e:
        log.warning("ElevenLabs TTS failed: %s", e)

def play_song() -> None:
    try:
        subprocess.Popen(
            [AIMP_EXE, TRACK_PATH],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError as e:
        log.warning("Could not launch AIMP: %s", e)


def _brave_executable() -> str | None:
    if sys.platform == "win32":
        for base in (
            os.environ.get("ProgramFiles", r"C:\Program Files"),
            os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
            os.environ.get("LOCALAPPDATA", ""),
        ):
            if not base:
                continue

            p = os.path.join(
                base,
                "BraveSoftware",
                "Brave-Browser",
                "Application",
                "brave.exe",
            )

            if os.path.isfile(p):
                return p

    return shutil.which("brave") or shutil.which("brave-browser")


def _win32_sorted_monitor_rects() -> list[tuple[int, int, int, int]]:
    """Each monitor as (left, top, right, bottom), sorted left-to-right then top-to-bottom."""
    if sys.platform != "win32":
        return []
    import ctypes
    from ctypes import wintypes

    class RECT(ctypes.Structure):
        _fields_ = [
            ("left", wintypes.LONG),
            ("top", wintypes.LONG),
            ("right", wintypes.LONG),
            ("bottom", wintypes.LONG),
        ]

    collected: list[tuple[int, int, int, int]] = []

    @ctypes.WINFUNCTYPE(
        wintypes.BOOL,
        wintypes.HMONITOR,
        wintypes.HDC,
        ctypes.POINTER(RECT),
        wintypes.LPARAM,
    )
    def _cb(_hm, _hdc, lprc, _lp):
        r = lprc.contents
        collected.append((int(r.left), int(r.top), int(r.right), int(r.bottom)))
        return True

    ctypes.windll.user32.EnumDisplayMonitors(None, None, _cb, 0)
    collected.sort(key=lambda t: (t[0], t[1]))
    return collected


def _brave_monitor_top_left(one_based_index: int) -> tuple[int, int]:
    """Top-left corner on virtual desktop for monitor N (1-based)."""
    l, t, _, _ = _brave_monitor_bounds(one_based_index)
    return (l, t)


def _brave_monitor_bounds(one_based_index: int) -> tuple[int, int, int, int]:
    """Monitor N as (left, top, right, bottom), 1-based index (sorted like other Brave helpers)."""
    rects = _win32_sorted_monitor_rects()
    if not rects:
        return (0, 0, 1920, 1080)
    idx = one_based_index - 1
    if idx < 0:
        idx = 0
    if idx >= len(rects):
        log.warning(
            "Monitor %d requested but only %d found; using last monitor.",
            one_based_index,
            len(rects),
        )
        idx = len(rects) - 1
    return rects[idx]


def _brave_monitor_pixel_size(one_based_index: int) -> tuple[int, int]:
    l, t, r, b = _brave_monitor_bounds(one_based_index)
    return (max(320, r - l), max(240, b - t))


def _brave_window_size() -> tuple[int, int]:
    w = (os.environ.get("BRAVE_WINDOW_WIDTH") or "1400").strip()
    h = (os.environ.get("BRAVE_WINDOW_HEIGHT") or "900").strip()
    try:
        return (max(400, int(w)), max(300, int(h)))
    except ValueError:
        return (1400, 900)


def _brave_site_user_data_dir(site_key: str) -> str:
    p = Path(tempfile.gettempdir()) / "clap-trigger-brave" / site_key
    p.mkdir(parents=True, exist_ok=True)
    return str(p)


def _brave_new_window_wait_timeout_s() -> float:
    try:
        return max(3.0, float((os.environ.get("BRAVE_NEW_WINDOW_WAIT_S") or "25").strip()))
    except ValueError:
        return 25.0


def _brave_top_level_browser_hwnds_win32() -> set[int]:
    """HWND ints for visible-or-minimized top-level Brave browser windows."""
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    GW_OWNER = 4
    GWL_EXSTYLE = -20
    WS_EX_TOOLWINDOW = 0x00000080
    found: set[int] = set()

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def _enum(hwnd: wintypes.HWND, _lp: wintypes.LPARAM) -> bool:
        if user32.GetWindow(hwnd, GW_OWNER):
            return True
        if user32.GetWindowLongW(hwnd, GWL_EXSTYLE) & WS_EX_TOOLWINDOW:
            return True
        if not user32.IsWindowVisible(hwnd) and not user32.IsIconic(hwnd):
            return True
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value == 0:
            return True
        hproc = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
        if not hproc:
            return True
        try:
            buf = ctypes.create_unicode_buffer(4096)
            sz = wintypes.DWORD(len(buf))
            if not kernel32.QueryFullProcessImageNameW(hproc, 0, buf, ctypes.byref(sz)):
                return True
            exe_path = buf.value
        finally:
            kernel32.CloseHandle(hproc)
        if os.path.basename(exe_path).lower() != "brave.exe":
            return True
        r = wintypes.RECT()
        if not user32.GetWindowRect(hwnd, ctypes.byref(r)):
            return True
        w, h = r.right - r.left, r.bottom - r.top
        if w < 80 or h < 80:
            return True
        found.add(int(hwnd))
        return True

    user32.EnumWindows(_enum, 0)
    return found


def _wait_new_brave_hwnd_win32(before: set[int], timeout: float) -> int | None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        time.sleep(0.12)
        now = _brave_top_level_browser_hwnds_win32()
        new = now - before
        if not new:
            continue
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        best: int | None = None
        best_area = 0
        for h in new:
            r = wintypes.RECT()
            if user32.GetWindowRect(h, ctypes.byref(r)):
                a = max(0, r.right - r.left) * max(0, r.bottom - r.top)
                if a > best_area:
                    best_area = a
                    best = h
        if best is not None:
            return best
    return None


def _brave_snap_window_to_monitor_win32(
    hwnd: int,
    one_based_monitor: int,
    *,
    fullscreen: bool,
    windowed_size: tuple[int, int] | None,
) -> None:
    import ctypes
    from ctypes import wintypes

    ml, mt, mr, mb = _brave_monitor_bounds(one_based_monitor)
    user32 = ctypes.windll.user32
    SW_RESTORE = 9
    SW_SHOWMAXIMIZED = 3
    HWND_TOP = 0
    SWP_SHOWWINDOW = 0x0040
    SWP_FRAMECHANGED = 0x0020
    flags = SWP_SHOWWINDOW | SWP_FRAMECHANGED

    user32.ShowWindow(hwnd, SW_RESTORE)
    if fullscreen:
        w, h = mr - ml, mb - mt
        x, y = ml, mt
    else:
        ww, wh = windowed_size or _brave_window_size()
        w, h = ww, wh
        x = ml + max(0, (mr - ml - w) // 2)
        y = mt + max(0, (mb - mt - h) // 2)
    user32.SetWindowPos(hwnd, HWND_TOP, x, y, w, h, flags)

    if fullscreen:
        user32.ShowWindow(hwnd, SW_SHOWMAXIMIZED)
        KEYEVENTF_KEYUP = 0x0002
        VK_F11 = 0x7A
        fg = user32.GetForegroundWindow()
        tid_tgt = user32.GetWindowThreadProcessId(hwnd, None)
        tid_fg = user32.GetWindowThreadProcessId(fg, None) if fg else 0
        if tid_fg and tid_tgt:
            user32.AttachThreadInput(tid_fg, tid_tgt, True)
        user32.SetForegroundWindow(hwnd)
        if tid_fg and tid_tgt:
            user32.AttachThreadInput(tid_fg, tid_tgt, False)
        user32.keybd_event(VK_F11, 0, 0, 0)
        user32.keybd_event(VK_F11, 0, KEYEVENTF_KEYUP, 0)


def _open_url_in_brave(
    url: str,
    *,
    new_window: bool = True,
    label: str = "URL",
    window_position: tuple[int, int] | None = None,
    window_size: tuple[int, int] | None = None,
    fullscreen: bool = False,
    win32_post_fullscreen_monitor: int | None = None,
    user_data_dir: str | None = None,
) -> None:
    u = url.strip()
    if not u:
        return
    brave = _brave_executable()
    try:
        if brave:
            args = [brave]
            if user_data_dir:
                args.append(f"--user-data-dir={user_data_dir}")
                args.append("--no-first-run")
            if new_window:
                args.append("--new-window")
            if window_position is not None:
                x, y = window_position
                args.append(f"--window-position={x},{y}")
            if window_size:
                args.append(f"--window-size={window_size[0]},{window_size[1]}")
            if fullscreen and not (
                sys.platform == "win32" and win32_post_fullscreen_monitor is not None
            ):
                args.append("--start-fullscreen")
            args.append(u)
            popen_kw: dict = {
                "args": args,
                "stdin": subprocess.DEVNULL,
                "stdout": subprocess.DEVNULL,
                "stderr": subprocess.DEVNULL,
            }
            if sys.platform == "win32":
                popen_kw["creationflags"] = subprocess.CREATE_NO_WINDOW
            before: set[int] | None = None
            if sys.platform == "win32" and win32_post_fullscreen_monitor is not None:
                before = _brave_top_level_browser_hwnds_win32()
            subprocess.Popen(**popen_kw)
            if sys.platform == "win32" and win32_post_fullscreen_monitor is not None:
                mon = win32_post_fullscreen_monitor
                hwnd = _wait_new_brave_hwnd_win32(before, _brave_new_window_wait_timeout_s())
                if hwnd is not None:
                    _brave_snap_window_to_monitor_win32(
                        hwnd,
                        mon,
                        fullscreen=fullscreen,
                        windowed_size=window_size if not fullscreen else None,
                    )
                else:
                    log.warning(
                        "Brave: timed out waiting for new window (%s); check "
                        "BRAVE_NEW_WINDOW_WAIT_S or close extra Brave instances.",
                        label,
                    )
        else:
            log.warning("Brave not found; opening %s in default browser.", label)
            webbrowser.open(u)
    except OSError as e:
        log.warning("Could not open %s in Brave: %s", label, e)


def open_chatgpt() -> None:
    if not OPEN_CHATGPT:
        return
    url = (os.environ.get("CHATGPT_URL") or "https://chatgpt.com").strip()
    pos: tuple[int, int] | None = None
    size: tuple[int, int] | None = None
    fs = OPEN_BRAVE_FULLSCREEN
    post_mon: int | None = None
    user_data: str | None = None
    if sys.platform == "win32":
        post_mon = CHATGPT_BRAVE_MONITOR
        pos = _brave_monitor_top_left(CHATGPT_BRAVE_MONITOR)
        if fs:
            size = _brave_monitor_pixel_size(CHATGPT_BRAVE_MONITOR)
        else:
            size = _brave_window_size()
        if BRAVE_SEPARATE_SITE_PROFILES:
            user_data = _brave_site_user_data_dir("chatgpt")
    elif not fs:
        size = _brave_window_size()
    else:
        size = None
    _open_url_in_brave(
        url,
        new_window=True,
        label="ChatGPT",
        window_position=pos,
        window_size=size,
        fullscreen=fs,
        win32_post_fullscreen_monitor=post_mon,
        user_data_dir=user_data,
    )


def open_tradingview() -> None:
    if not OPEN_TRADINGVIEW:
        return
    url = (
        os.environ.get("TRADINGVIEW_URL")
        or "https://in.tradingview.com/chart/GmjweavQ/?symbol=NSE%3ANIFTY"
    ).strip()
    pos: tuple[int, int] | None = None
    size: tuple[int, int] | None = None
    fs = OPEN_BRAVE_FULLSCREEN
    post_mon: int | None = None
    user_data: str | None = None
    if sys.platform == "win32":
        post_mon = TRADINGVIEW_BRAVE_MONITOR
        pos = _brave_monitor_top_left(TRADINGVIEW_BRAVE_MONITOR)
        if fs:
            size = _brave_monitor_pixel_size(TRADINGVIEW_BRAVE_MONITOR)
        else:
            size = _brave_window_size()
        if BRAVE_SEPARATE_SITE_PROFILES:
            user_data = _brave_site_user_data_dir("tradingview")
    elif not fs:
        size = _brave_window_size()
    else:
        size = None
    _open_url_in_brave(
        url,
        new_window=True,
        label="TradingView",
        window_position=pos,
        window_size=size,
        fullscreen=fs,
        win32_post_fullscreen_monitor=post_mon,
        user_data_dir=user_data,
    )


def run_double_clap_actions() -> None:
    """Run outside the mic loop so sleeps do not stall capture."""
    open_chatgpt()
    open_tradingview()
    if WELCOME_ENABLED:
        delay = max(0.0, AFTER_SONG_DELAY_S)
        if delay:
            time.sleep(delay)
        say_welcome()
    play_song()


def main() -> int:
    blocksize = block_samples()
    noise_floor = 1e-4
    last_logged_double = 0.0
    first_clap_time: float | None = None
    spike_armed = True
    welcome_sequence_done = False

    log.info(
        "Listening (double clap: %.2f–%.2fs apart, rate=%d, block=%d ms, "
        "spike_ratio=%.1f, cooldown=%.2fs). Ctrl+C to stop.",
        MIN_DOUBLE_GAP_S,
        MAX_DOUBLE_GAP_S,
        SAMPLE_RATE,
        BLOCK_MS,
        SPIKE_RATIO,
        COOLDOWN_S,
    )
    if OPEN_CHATGPT:
        chatgpt_url = (os.environ.get("CHATGPT_URL") or "https://chatgpt.com").strip()
        log.info(
            "After Spotify, open ChatGPT in Brave%s on monitor %d: %s",
            " fullscreen" if OPEN_BRAVE_FULLSCREEN else "",
            CHATGPT_BRAVE_MONITOR,
            chatgpt_url,
        )
    if OPEN_TRADINGVIEW:
        tradingview_url = (
            os.environ.get("TRADINGVIEW_URL")
            or "https://in.tradingview.com/chart/GmjweavQ/?symbol=NSE%3ANIFTY"
        ).strip()
        log.info(
            "After Spotify, open TradingView in Brave%s on monitor %d: %s",
            " fullscreen" if OPEN_BRAVE_FULLSCREEN else "",
            TRADINGVIEW_BRAVE_MONITOR,
            tradingview_url,
        )
    if WELCOME_ENABLED:
        ev, em, ef, er = elevenlabs_env_config()
        log.info(
            "After song + %.2fs: (ElevenLabs voice=%s, model=%s, format=%s, pcm_rate=%d)",
            AFTER_SONG_DELAY_S,
            ev or "(unset)",
            em,
            ef,
            er,
        )

    try:
        with sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype="float32",
            blocksize=blocksize,
        ) as stream:
            while True:
                data, overflowed = stream.read(blocksize)
                if overflowed:
                    log.warning("Input overflow; try a larger BLOCK_MS")

                level = rms_mono(data)

                quiet_gate = noise_floor * QUIET_GATE_MULT
                if level < quiet_gate:
                    noise_floor = NOISE_FLOOR_ALPHA * noise_floor + (
                        1.0 - NOISE_FLOOR_ALPHA
                    ) * level
                    noise_floor = max(noise_floor, 1e-7)

                threshold = max(noise_floor * SPIKE_RATIO, MIN_RMS)
                now = time.monotonic()
                retrigger_level = threshold * RETRIGGER_RATIO

                if level < retrigger_level:
                    spike_armed = True

                if (
                    spike_armed
                    and level >= threshold
                    and (now - last_logged_double) >= COOLDOWN_S
                ):
                    spike_armed = False
                    if first_clap_time is None:
                        first_clap_time = now
                    else:
                        gap = now - first_clap_time
                        if gap < MIN_DOUBLE_GAP_S:
                            pass
                        elif gap <= MAX_DOUBLE_GAP_S:
                            first_clap_time = None
                            last_logged_double = now
                            if not welcome_sequence_done:
                                welcome_sequence_done = True
                                log.info(
                                    "Double clap detected (gap=%.3fs, rms=%.5f, "
                                    "noise_floor=%.5f, threshold=%.5f) — running welcome once",
                                    gap,
                                    level,
                                    noise_floor,
                                    threshold,
                                )
                                threading.Thread(
                                    target=run_double_clap_actions,
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
