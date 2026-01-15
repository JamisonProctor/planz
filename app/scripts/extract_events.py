from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from app.db.models.source_url import SourceUrl
from app.db.session import get_session
from app.services.extract.llm_event_extractor import extract_events_from_text
from app.services.extract.store_extracted_events import store_extracted_events


def main() -> None:
    now = datetime.now(tz=timezone.utc)
    total_sources = 0
    total_events = 0

    session_gen = get_session()
    session = next(session_gen)
    try:
        sources = session.scalars(
            select(SourceUrl).where(
                SourceUrl.fetch_status == "ok",
                SourceUrl.content_excerpt.is_not(None),
            )
        ).all()

        for source_url in sources:
            total_sources += 1
            extracted = extract_events_from_text(
                source_url.content_excerpt or "", source_url.url
            )
            created = store_extracted_events(session, source_url, extracted, now=now)
            total_events += created

        session.commit()
    finally:
        try:
            next(session_gen)
        except StopIteration:
            pass

    print(f"Sources processed: {total_sources}")
    print(f"Events created: {total_events}")


if __name__ == "__main__":
    main()
