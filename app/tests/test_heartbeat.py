import logging
import time

from app.utils.heartbeat import start_heartbeat


def test_heartbeat_emits_and_stops(monkeypatch, caplog) -> None:
    caplog.set_level(logging.INFO)
    now = [0.0]

    def fake_monotonic():
        return now[0]

    def fake_wait(stop_event, interval):
        now[0] += interval
        return stop_event.is_set()

    stop = start_heartbeat(
        "llm",
        interval_s=1.0,
        logger=logging.getLogger("hbtest"),
        time_fn=fake_monotonic,
        wait_fn=fake_wait,
    )

    time.sleep(0.01)  # allow thread to start
    time.sleep(0.01)
    stop()

    messages = [rec.message for rec in caplog.records if "hbtest" in rec.name]
    assert any("still running step=llm" in msg for msg in messages)
