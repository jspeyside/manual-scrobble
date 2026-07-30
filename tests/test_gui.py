from datetime import datetime

import pytest

import gui


# ---------- _format_time ----------

def test_format_time_no_leading_zero():
    ts = int(datetime(2026, 7, 30, 20, 40).timestamp())
    assert gui._format_time(ts) == "8:40 PM"


def test_format_time_midnight():
    ts = int(datetime(2026, 7, 30, 0, 0).timestamp())
    assert gui._format_time(ts) == "12:00 AM"


def test_format_time_noon():
    ts = int(datetime(2026, 7, 30, 12, 0).timestamp())
    assert gui._format_time(ts) == "12:00 PM"


# ---------- parse_finished_at ----------

def test_parse_finished_at_valid():
    expected = int(datetime(2026, 7, 30, 21, 0).timestamp())
    assert gui.parse_finished_at("2026-07-30", "09:00 PM") == expected


def test_parse_finished_at_lowercase_am_pm():
    expected = int(datetime(2026, 7, 30, 9, 0).timestamp())
    assert gui.parse_finished_at("2026-07-30", "09:00 am") == expected


def test_parse_finished_at_rejects_24hr_input():
    with pytest.raises(ValueError, match="AM/PM"):
        gui.parse_finished_at("2026-07-30", "21:00")


def test_parse_finished_at_invalid_input_raises_friendly_message():
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        gui.parse_finished_at("garbage", "garbage")


# ---------- select_tracks ----------

def test_select_tracks_preserves_album_order_regardless_of_selection_order():
    tracks = [{"ratingKey": "1"}, {"ratingKey": "2"}, {"ratingKey": "3"}]
    result = gui.select_tracks(tracks, {"3", "1"})
    assert [t["ratingKey"] for t in result] == ["1", "3"]


def test_select_tracks_empty_selection_returns_empty_list():
    tracks = [{"ratingKey": "1"}]
    assert gui.select_tracks(tracks, set()) == []


def test_select_tracks_ignores_unknown_keys():
    tracks = [{"ratingKey": "1"}, {"ratingKey": "2"}]
    result = gui.select_tracks(tracks, {"1", "999"})
    assert [t["ratingKey"] for t in result] == ["1"]
