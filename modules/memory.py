import json
from pathlib import Path

MEMORY_FILE = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "memory.json"
)


def load_memory():
    try:
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}