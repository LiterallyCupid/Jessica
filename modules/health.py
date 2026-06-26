from pathlib import Path
from datetime import datetime, timedelta

from openpyxl import load_workbook

WORKBOOK = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "FRIDAY_HEALTH_CORE.xlsx"
)


def generate_health_briefing(memory):
    wb = load_workbook(WORKBOOK, data_only=True)

    workout = wb["Workout Log"]
    metrics = wb["Body Metrics"]
    nutrition = wb["Nutrition"]

    briefing = []

    return briefing