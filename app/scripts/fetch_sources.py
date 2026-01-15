from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from app.db.models.source_domain import SourceDomain
from app.db.models.source_url import SourceUrl
from app.db.session import get_session
from app.services.fetch.http_fetcher import fetch_url_text
from app.services.fetch.store_fetch_result import store_fetch_result


def main() -> None:
    ok_count = 0
    error_count = 0
    now = datetime.now(tz=timezone.utc)

    session_gen = get_session()
    session = next(session_gen)
    try:
        urls = session.scalars(
            select(SourceUrl)
            .join(SourceDomain, SourceDomain.id == SourceUrl.domain_id)
            .where(SourceDomain.is_allowed.is_(True))
        ).all()

        for source_url in urls:
            text, error = fetch_url_text(source_url.url)
            store_fetch_result(session, source_url, text=text, error=error, now=now)
            if text is not None:
                ok_count += 1
            else:
                error_count += 1

        session.commit()
    finally:
        try:
            next(session_gen)
        except StopIteration:
            pass

    print(f"Fetched OK: {ok_count}")
    print(f"Fetched errors: {error_count}")


if __name__ == "__main__":
    main()
