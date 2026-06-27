from __future__ import annotations
from pathlib import Path
from datetime import datetime,timedelta
from openpyxl import load_workbook

WORKBOOK = (
    Path(__file__).resolve().parent.parent
    / "data"
    /"friday_health_core.xlsx"
)

def _load_sheets():
    wb=load_workbook(WORKBOOK,data_only=True)
    return(
        wb["Workout Log"],
        wb["Body Metrics"],
        wb["Nutrition"]
    )

def _latest_weight(metrics_sheet):

    latest = None

    for row in metrics_sheet.iter_rows(
        min_row=2,
        values_only=True,
    ):
        date, weight = row[:2]

        if date and weight is not None:
            latest = weight

    return latest

def generate_health_briefing():

    workout_sheet, metrics_sheet, nutrition_sheet = _load_sheets()

    briefing = []

    weight = _latest_weight(metrics_sheet)

    if weight is not None:

        briefing.append(
            f"Your current weight is {weight:.1f} kilograms."
        )

    return briefing