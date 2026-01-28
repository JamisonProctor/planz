import logging

from app.utils.timing import RunStats


def test_run_stats_logs_status(caplog) -> None:
    caplog.set_level(logging.INFO)
    stats = RunStats(
        page_index=1,
        page_total=3,
        fetch_s=1.2,
        extract_s=2.3,
        persist_s=0.4,
        sync_s=0.1,
        events_extracted=5,
        events_new=4,
        events_updated=1,
        errors_count=0,
        total_elapsed_s=4.0,
    )
    stats.log_status(logging.getLogger("status-test"))

    assert any("[1/3]" in rec.message and "events=5" in rec.message for rec in caplog.records)
