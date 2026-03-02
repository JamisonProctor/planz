from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.services.extract.weekend_slicer import classify_event_time

TZ = ZoneInfo("Europe/Berlin")


def dt(day: date, hour: int, minute: int = 0) -> datetime:
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=TZ)


# --- Weekends always candidate, no adjustment ---

def test_saturday_always_candidate() -> None:
    day = date(2026, 3, 7)  # Saturday
    is_candidate, effective_start = classify_event_time(day, dt(day, 10), dt(day, 12))
    assert is_candidate is True
    assert effective_start.hour == 10


def test_sunday_always_candidate() -> None:
    day = date(2026, 3, 8)  # Sunday
    is_candidate, effective_start = classify_event_time(day, dt(day, 9), dt(day, 11))
    assert is_candidate is True
    assert effective_start.hour == 9


# --- Mon-Thu: threshold 16:00, extended if ends >= 17:00 ---

def test_weekday_evening_start_is_candidate() -> None:
    day = date(2026, 3, 3)  # Tuesday
    is_candidate, effective_start = classify_event_time(day, dt(day, 19, 30), dt(day, 21, 30))
    assert is_candidate is True
    assert effective_start.hour == 19
    assert effective_start.minute == 30


def test_weekday_afternoon_start_at_threshold_is_candidate() -> None:
    day = date(2026, 3, 3)  # Tuesday
    is_candidate, effective_start = classify_event_time(day, dt(day, 16), dt(day, 18))
    assert is_candidate is True
    assert effective_start.hour == 16


def test_weekday_starts_early_ends_after_threshold_plus_one_is_candidate_adjusted() -> None:
    day = date(2026, 3, 3)  # Tuesday, starts 14:00 ends 18:00
    is_candidate, effective_start = classify_event_time(day, dt(day, 14), dt(day, 18))
    assert is_candidate is True
    assert effective_start.hour == 16
    assert effective_start.minute == 0


def test_weekday_starts_early_ends_exactly_at_threshold_plus_one_is_candidate_adjusted() -> None:
    day = date(2026, 3, 3)  # Tuesday, starts 10:00 ends 17:00
    is_candidate, effective_start = classify_event_time(day, dt(day, 10), dt(day, 17))
    assert is_candidate is True
    assert effective_start.hour == 16


def test_weekday_morning_only_is_not_candidate() -> None:
    day = date(2026, 3, 3)  # Tuesday, starts 10:00 ends 12:00
    is_candidate, _ = classify_event_time(day, dt(day, 10), dt(day, 12))
    assert is_candidate is False


def test_weekday_no_end_time_defaults_to_two_hours_for_classification() -> None:
    day = date(2026, 3, 3)  # Tuesday, starts 15:30, no end → effective end 17:30
    is_candidate, effective_start = classify_event_time(day, dt(day, 15, 30), None)
    assert is_candidate is True
    assert effective_start.hour == 16
    assert effective_start.minute == 0


def test_weekday_no_end_time_morning_is_not_candidate() -> None:
    day = date(2026, 3, 3)  # Tuesday, starts 10:00, no end → effective end 12:00
    is_candidate, _ = classify_event_time(day, dt(day, 10), None)
    assert is_candidate is False


# --- Friday: threshold 12:00, extended if ends >= 13:00 ---

def test_friday_after_noon_is_candidate() -> None:
    day = date(2026, 3, 6)  # Friday
    is_candidate, effective_start = classify_event_time(day, dt(day, 14), dt(day, 16))
    assert is_candidate is True
    assert effective_start.hour == 14


def test_friday_morning_ending_after_threshold_plus_one_is_candidate_adjusted() -> None:
    day = date(2026, 3, 6)  # Friday, starts 10:00 ends 14:00
    is_candidate, effective_start = classify_event_time(day, dt(day, 10), dt(day, 14))
    assert is_candidate is True
    assert effective_start.hour == 12
    assert effective_start.minute == 0


def test_friday_morning_only_is_not_candidate() -> None:
    day = date(2026, 3, 6)  # Friday, starts 09:00 ends 11:00
    is_candidate, _ = classify_event_time(day, dt(day, 9), dt(day, 11))
    assert is_candidate is False
