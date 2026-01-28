from __future__ import annotations

from dataclasses import dataclass, field
from time import monotonic
from typing import Iterator


def format_duration(seconds: float) -> str:
    total = int(seconds)
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    parts = []
    if hours:
        parts.append(f"{hours}h")
    if minutes or hours:
        parts.append(f"{minutes}m")
    parts.append(f"{secs}s")
    return "".join(parts)


class Timer:
    def __init__(self, name: str = "") -> None:
        self.name = name
        self.start = 0.0
        self.elapsed = 0.0

    def __enter__(self) -> "Timer":
        self.start = monotonic()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.elapsed = monotonic() - self.start


@dataclass
class RunStats:
    page_index: int = 0
    page_total: int = 0
    fetch_s: float = 0.0
    extract_s: float = 0.0
    persist_s: float = 0.0
    sync_s: float = 0.0
    events_extracted: int = 0
    events_new: int = 0
    events_updated: int = 0
    errors_count: int = 0
    total_elapsed_s: float = 0.0

    @classmethod
    def combine(cls, runs: list["RunStats"]) -> "RunStats":
        combined = cls()
        combined.page_total = len(runs)
        combined.fetch_s = sum(r.fetch_s for r in runs)
        combined.extract_s = sum(r.extract_s for r in runs)
        combined.persist_s = sum(r.persist_s for r in runs)
        combined.sync_s = sum(r.sync_s for r in runs)
        combined.events_extracted = sum(r.events_extracted for r in runs)
        combined.events_new = sum(r.events_new for r in runs)
        combined.events_updated = sum(r.events_updated for r in runs)
        combined.errors_count = sum(r.errors_count for r in runs)
        combined.total_elapsed_s = sum(r.total_elapsed_s for r in runs)
        return combined

    def status_line(self) -> str:
        return (
            f"[{self.page_index}/{self.page_total}] "
            f"fetch={format_duration(self.fetch_s)} "
            f"extract={format_duration(self.extract_s)} "
            f"persist={format_duration(self.persist_s)} "
            f"sync={format_duration(self.sync_s)} | "
            f"events={self.events_extracted} new={self.events_new} "
            f"updated={self.events_updated} errors={self.errors_count} | "
            f"total={format_duration(self.total_elapsed_s)}"
        )

    def log_status(self, logger) -> None:
        logger.info(self.status_line())
