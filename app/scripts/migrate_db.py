from __future__ import annotations

from datetime import datetime, timezone

from app.core.env import load_env
from app.db.migrations.sqlite import ensure_sqlite_schema
from app.db.session import engine
from app.logging import configure_logging


def main() -> None:
    load_env()
    configure_logging()
    ensure_sqlite_schema(engine)
    print(f"Migration completed at {datetime.now(tz=timezone.utc).isoformat()}")


if __name__ == "__main__":
    main()
