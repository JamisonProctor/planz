import time

from app.utils.timing import Timer, format_duration


def test_format_duration_formats_components() -> None:
    assert format_duration(5) == "5s"
    assert format_duration(61) == "1m1s"
    assert format_duration(3723) == "1h2m3s"


def test_timer_measures_elapsed(monkeypatch) -> None:
    now = [0.0]

    def fake_monotonic():
        return now[0]

    monkeypatch.setattr("app.utils.timing.monotonic", fake_monotonic)
    with Timer() as t:
        now[0] = 5.0
    assert t.elapsed == 5.0

