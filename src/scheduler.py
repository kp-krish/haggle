"""Pickup scheduling: intersect both students' free windows and pick a public spot.

A plain algorithm, not the model. Pure Python: no AWS or Discord imports.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from pathlib import Path

MIN_SLOT_MINUTES = 20
HORIZON_DAYS = 7
DAYLIGHT = (time(8, 0), time(19, 0))
SLOT_STEP_MINUTES = 5

PLACES_PATH = Path(__file__).resolve().parent / "data" / "places.json"
CAMPUS_TZ = timezone(timedelta(hours=-7), "MST")  # Arizona: no daylight saving


@dataclass(frozen=True, order=True)
class Window:
    start: datetime
    end: datetime

    @property
    def minutes(self) -> float:
        return (self.end - self.start).total_seconds() / 60


@dataclass(frozen=True)
class Pickup:
    slot: Window
    place: dict


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=CAMPUS_TZ)


def merge(windows: list[Window]) -> list[Window]:
    """Sort and merge overlapping or touching windows."""
    merged: list[Window] = []
    for w in sorted(windows):
        if merged and w.start <= merged[-1].end:
            merged[-1] = Window(merged[-1].start, max(merged[-1].end, w.end))
        else:
            merged.append(w)
    return merged


def validate_windows(
    raw: list[dict], now: datetime, horizon_days: int = HORIZON_DAYS
) -> list[Window]:
    """Turn the model's ``[{"start": iso, "end": iso}, ...]`` into clean windows.

    Drops anything malformed, in the past, beyond the horizon or too short.
    Naive times are read as campus time.
    """
    now = _aware(now)
    horizon = now + timedelta(days=horizon_days)
    windows = []
    for item in raw:
        try:
            start = _aware(datetime.fromisoformat(item["start"]))
            end = _aware(datetime.fromisoformat(item["end"]))
        except (KeyError, TypeError, ValueError):
            continue
        start, end = max(start, now), min(end, horizon)
        if (end - start) >= timedelta(minutes=MIN_SLOT_MINUTES):
            windows.append(Window(start, end))
    return merge(windows)


def intersect(
    a: list[Window], b: list[Window], min_minutes: int = MIN_SLOT_MINUTES
) -> list[Window]:
    """Overlaps of two window lists that are at least ``min_minutes`` long."""
    a, b = merge(a), merge(b)
    out, i, j = [], 0, 0
    while i < len(a) and j < len(b):
        start, end = max(a[i].start, b[j].start), min(a[i].end, b[j].end)
        if (end - start) >= timedelta(minutes=min_minutes):
            out.append(Window(start, end))
        if a[i].end < b[j].end:
            i += 1
        else:
            j += 1
    return out


def clip_to_daylight(windows: list[Window]) -> list[Window]:
    """Keep only the parts of each window between 8 am and 7 pm campus time."""
    out = []
    for w in windows:
        day = w.start.astimezone(CAMPUS_TZ).date()
        last = w.end.astimezone(CAMPUS_TZ).date()
        while day <= last:
            lo = datetime.combine(day, DAYLIGHT[0], CAMPUS_TZ)
            hi = datetime.combine(day, DAYLIGHT[1], CAMPUS_TZ)
            start, end = max(w.start, lo), min(w.end, hi)
            if end > start:
                out.append(Window(start, end))
            day += timedelta(days=1)
    return out


def _round_up(dt: datetime, minutes: int = SLOT_STEP_MINUTES) -> datetime:
    dt = dt.replace(second=0, microsecond=0) + (
        timedelta(minutes=1) if dt.second or dt.microsecond else timedelta()
    )
    return dt + timedelta(minutes=(-dt.minute) % minutes)


def earliest_slot(
    a: list[Window],
    b: list[Window],
    min_minutes: int = MIN_SLOT_MINUTES,
    not_before: datetime | None = None,
) -> Window | None:
    """Earliest ``min_minutes`` slot both sides can make, preferring daylight hours.

    Slots start on a 5-minute mark so pickup times read naturally (4:30, not 4:27).
    ``not_before`` leaves lead time for confirmations and the reminder.
    """
    if not_before is not None:
        a = [Window(max(w.start, not_before), w.end) for w in a if w.end > not_before]
        b = [Window(max(w.start, not_before), w.end) for w in b if w.end > not_before]
    overlaps = intersect(a, b, min_minutes)
    for candidates in (clip_to_daylight(overlaps), overlaps):
        for w in candidates:
            start = _round_up(w.start)
            end = start + timedelta(minutes=min_minutes)
            if end <= w.end:
                return Window(start, end)
    return None


def format_slot(dt: datetime) -> str:
    """Campus-time label like "Thu Oct 29, 4:30 pm" (portable: no %-I on Windows)."""
    local = dt.astimezone(CAMPUS_TZ)
    hour = local.strftime("%I").lstrip("0")
    return f"{local:%a %b} {local.day}, {hour}:{local:%M} {local:%p}".replace("AM", "am").replace(
        "PM", "pm"
    )


def windows_from_records(raw: list[dict] | None) -> list[Window]:
    """Stored ``[{"start": iso, "end": iso}]`` back into windows (bad entries skipped)."""
    out = []
    for item in raw or []:
        try:
            out.append(
                Window(
                    _aware(datetime.fromisoformat(item["start"])),
                    _aware(datetime.fromisoformat(item["end"])),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    return merge(out)


def load_places(path: Path = PLACES_PATH) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _distance_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Equirectangular approximation; plenty accurate across one campus."""
    x = math.radians(lng2 - lng1) * math.cos(math.radians((lat1 + lat2) / 2))
    y = math.radians(lat2 - lat1)
    return 6_371_000 * math.hypot(x, y)


def choose_spot(places: dict, area_a: str, area_b: str, large: bool = False) -> dict:
    """Public spot closest to both students' campus areas. Large items need curbside."""
    areas = places["areas"]
    centre = places["areas"].get("central") or next(iter(areas.values()))
    pa, pb = areas.get(area_a, centre), areas.get(area_b, centre)
    candidates = [p for p in places["places"] if p["curbside"] or not large]
    if not candidates:
        candidates = places["places"]

    def score(p: dict) -> tuple[float, str]:
        d = _distance_m(p["lat"], p["lng"], pa["lat"], pa["lng"]) + _distance_m(
            p["lat"], p["lng"], pb["lat"], pb["lng"]
        )
        return d, p["place_id"]

    return min(candidates, key=score)


def schedule(
    a: list[Window],
    b: list[Window],
    area_a: str,
    area_b: str,
    large: bool = False,
    places: dict | None = None,
    not_before: datetime | None = None,
) -> Pickup | None:
    """Earliest shared slot plus meeting spot, or None when the windows never overlap."""
    slot = earliest_slot(a, b, not_before=not_before)
    if slot is None:
        return None
    return Pickup(slot, choose_spot(places or load_places(), area_a, area_b, large))
