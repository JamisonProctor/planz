import logging
import os


def configure_logging(level: str | None = None) -> None:
    env_level = os.getenv("LOG_LEVEL")
    chosen = (level or env_level or "INFO").upper()
    logging.basicConfig(
        level=getattr(logging, chosen, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    for noisy in ["httpx", "urllib3", "googleapiclient", "google.auth"]:
        logging.getLogger(noisy).setLevel(logging.WARNING)
