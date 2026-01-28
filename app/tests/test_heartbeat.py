import logging
import time

from app.utils.heartbeat import start_heartbeat


def test_heartbeat_emits_and_stops(monkeypatch, caplog) -> None:
    caplog.set_level(logging.INFO)
    now = [0.0]

    def fake_monotonic():
        return now[0]

    def fake_sleep(interval):
        now[0] += interval

    stop = start_heartbeat(
        "llm",
        interval_s=1.0,
        logger=logging.getLogger("hbtest"),
        time_fn=fake_monotonic,
        sleep_fn=fake_sleep,
    )

    time.sleep(0.01)  # allow thread to start
    fake_sleep(1.0)
    time.sleep(0.01)
    stop()

    messages = [rec.message for rec in caplog.records if "hbtest" in rec.name]
    assert any("still running step=llm" in msg for msg in messages)

