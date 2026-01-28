from __future__ import annotations

import logging
import threading
import time
from typing import Callable

from app.utils.timing import format_duration


def start_heartbeat(
    step_label: str,
    interval_s: float = 30.0,
    logger: logging.Logger | None = None,
    time_fn: Callable[[], float] = time.monotonic,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> Callable[[], None]:
    log = logger or logging.getLogger(__name__)
    if interval_s is None or log.isEnabledFor(logging.DEBUG):
        return lambda: None

    stop_event = threading.Event()
    start_time = time_fn()

    def _run() -> None:
        while not stop_event.is_set():
            sleep_fn(interval_s)
            if stop_event.is_set():
                break
            elapsed = time_fn() - start_time
            log.info("...still running step=%s elapsed=%s", step_label, format_duration(elapsed))

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()

    def stop() -> None:
        stop_event.set()
        thread.join()

    return stop
