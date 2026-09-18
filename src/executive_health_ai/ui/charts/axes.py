"""Visible axes for every formal health time-series chart, independent of theme."""
import altair as alt
from datetime import datetime, timezone


AXIS_INK = "#334155"
GRID = "#E2E8F0"
CHART_PADDING = {"left": 18, "right": 22, "top": 12, "bottom": 18}


def health_axis_config():
    return {
        "domain": True, "ticks": True, "labels": True,
        "domainColor": AXIS_INK, "domainWidth": 2,
        "tickColor": AXIS_INK, "tickWidth": 2, "tickSize": 7,
        "labelColor": AXIS_INK, "labelFontSize": 13, "labelFontWeight": 500,
        "titleColor": AXIS_INK, "titleFontSize": 13, "titleFontWeight": 600,
        "labelPadding": 7, "titlePadding": 12,
        "gridColor": GRID, "gridWidth": 1,
    }


def time_axis_config(date_format, *, dates=(), compact=False):
    options = dict(health_axis_config(), title="时间", format=date_format,
                   grid=False, labelAngle=0, labelOverlap="greedy",
                   labelFlush=False, tickCount=3 if compact else 5)
    # Put labels at actual observation dates, including both endpoints. Automatic
    # quarterly ticks previously left an eight-month baseline with only 2 labels.
    stamps = sorted({int(at.timestamp() * 1000) for at in dates})
    if stamps:
        count = min(len(stamps), 3 if compact else 5)
        span = stamps[-1] - stamps[0]
        targets = [stamps[0] + span*i/max(count-1, 1) for i in range(count)]
        candidates = sorted({min(stamps, key=lambda value: abs(value-target)) for target in targets})
        spaced = [stamps[0]]
        for value in candidates[1:-1]:
            if value-spaced[-1] >= span*.12 and stamps[-1]-value >= span*.12:
                spaced.append(value)
        if stamps[-1] != spaced[-1]:
            spaced.append(stamps[-1])
        # Vega-Lite interprets numeric temporal axis values as calendar years,
        # not epoch milliseconds. DateTime objects retain the actual instant.
        selected = [datetime.fromtimestamp(value / 1000, timezone.utc) for value in spaced]
        options["values"] = [alt.DateTime(utc=True, year=at.year, month=at.month,
            date=at.day, hours=at.hour, minutes=at.minute, seconds=at.second,
            milliseconds=at.microsecond // 1000) for at in selected]
    return alt.Axis(**options)


def numeric_axis_config(unit, *, title=None, compact=False):
    return alt.Axis(**dict(health_axis_config(), title=title or unit,
                          grid=True, tickCount=3 if compact else 5, minExtent=48))
