from __future__ import annotations

import logging
import threading
import time
from typing import Callable

from app.utils.timing import format_duration


def _default_wait(stop_event: threading.Event, interval_s: float) -> bool:
    return stop_event.wait(interval_s)


def start_heartbeat(
    step_label: str,
    interval_s: float = 30.0,
    logger: logging.Logger | None = None,
    time_fn: Callable[[], float] = time.monotonic,
    wait_fn: Callable[[threading.Event, float], bool] = _default_wait,
) -> Callable[[], None]:
    log = logger or logging.getLogger(__name__)
    if interval_s is None or log.isEnabledFor(logging.DEBUG):
        return lambda: None

    stop_event = threading.Event()
    start_time = time_fn()

    def _run() -> None:
        while not stop_event.is_set():
            if wait_fn(stop_event, interval_s):
                break
            elapsed = time_fn() - start_time
            log.info("...still running step=%s elapsed=%s", step_label, format_duration(elapsed))

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()

    def stop() -> None:
        stop_event.set()
        thread.join()

    return stop
