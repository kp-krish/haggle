from datetime import datetime, timedelta

from scheduler import (
    CAMPUS_TZ,
    Window,
    choose_spot,
    clip_to_daylight,
    earliest_slot,
    intersect,
    load_places,
    schedule,
    validate_windows,
)


def at(day, hour, minute=0):
    return datetime(2026, 10, day, hour, minute, tzinfo=CAMPUS_TZ)


def test_intersect_keeps_overlaps_of_at_least_20_minutes():
    a = [Window(at(29, 15), at(29, 17)), Window(at(30, 9), at(30, 9, 15))]
    b = [Window(at(29, 16, 30), at(29, 18)), Window(at(30, 9), at(30, 10))]
    assert intersect(a, b) == [Window(at(29, 16, 30), at(29, 17))]


def test_no_overlap_returns_none():
    a = [Window(at(29, 9), at(29, 10))]
    b = [Window(at(29, 14), at(29, 15))]
    assert earliest_slot(a, b) is None


def test_earliest_slot_starts_on_a_five_minute_mark():
    a = [Window(at(29, 16, 27), at(29, 18))]
    b = [Window(at(29, 15), at(29, 17))]
    assert earliest_slot(a, b) == Window(at(29, 16, 30), at(29, 16, 50))


def test_daylight_slot_is_preferred_over_an_earlier_night_slot():
    a = [Window(at(29, 22), at(29, 23)), Window(at(30, 10), at(30, 11))]
    b = [Window(at(29, 22), at(29, 23)), Window(at(30, 10), at(30, 11))]
    assert earliest_slot(a, b).start == at(30, 10)


def test_night_slot_used_when_nothing_else_fits():
    a = [Window(at(29, 21), at(29, 22))]
    assert earliest_slot(a, a).start == at(29, 21)


def test_clip_to_daylight_splits_across_days():
    clipped = clip_to_daylight([Window(at(29, 17), at(30, 9))])
    assert clipped == [Window(at(29, 17), at(29, 19)), Window(at(30, 8), at(30, 9))]


def test_validate_windows_drops_bad_past_and_far_entries():
    now = at(24, 12)
    raw = [
        {"start": "2026-10-26T15:00:00-07:00", "end": "2026-10-26T17:00:00-07:00"},
        {"start": "2026-10-20T15:00:00-07:00", "end": "2026-10-20T17:00:00-07:00"},
        {"start": "2026-12-01T15:00:00-07:00", "end": "2026-12-01T17:00:00-07:00"},
        {"start": "not a time", "end": "2026-10-26T17:00:00"},
        {"start": "2026-10-27T10:00:00", "end": "2026-10-27T10:10:00"},
        {"end": "2026-10-27T10:10:00"},
    ]
    assert validate_windows(raw, now) == [Window(at(26, 15), at(26, 17))]


def test_validate_windows_clips_to_now_and_merges():
    now = at(24, 12)
    raw = [
        {"start": "2026-10-24T11:00:00", "end": "2026-10-24T13:00:00"},
        {"start": "2026-10-24T12:30:00", "end": "2026-10-24T14:00:00"},
    ]
    assert validate_windows(raw, now) == [Window(now, now + timedelta(hours=2))]


def test_spot_is_between_both_areas():
    places = load_places()
    assert choose_spot(places, "south", "south")["area"] == "south"
    assert choose_spot(places, "north", "north")["area"] == "north"


def test_large_items_get_curbside_spots():
    places = load_places()
    for a in places["areas"]:
        for b in places["areas"]:
            assert choose_spot(places, a, b, large=True)["curbside"]


def test_unknown_area_falls_back_to_central():
    assert choose_spot(load_places(), "mars", "central")["place_id"]


def test_schedule_returns_slot_and_place():
    a = [Window(at(29, 15), at(29, 18))]
    b = [Window(at(29, 16, 30), at(29, 20))]
    pickup = schedule(a, b, "central", "central")
    assert pickup.slot.start == at(29, 16, 30)
    assert pickup.place["place_id"] == "mu-north"


def test_format_slot_reads_naturally():
    from scheduler import format_slot

    assert format_slot(at(29, 16, 30)) == "Thu Oct 29, 4:30 pm"
    assert format_slot(at(29, 9)) == "Thu Oct 29, 9:00 am"


def test_windows_from_records_skips_bad_entries():
    from scheduler import windows_from_records

    raw = [
        {"start": at(29, 15).isoformat(), "end": at(29, 17).isoformat()},
        {"start": "nope"},
        {"start": at(29, 16).isoformat(), "end": at(29, 18).isoformat()},
    ]
    assert windows_from_records(raw) == [Window(at(29, 15), at(29, 18))]
    assert windows_from_records(None) == []


def test_not_before_leaves_lead_time():
    a = [Window(at(29, 15), at(29, 18))]
    assert earliest_slot(a, a, not_before=at(29, 16, 2)).start == at(29, 16, 5)
    assert earliest_slot(a, a, not_before=at(29, 17, 50)) is None
