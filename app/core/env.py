import os

from dotenv import load_dotenv


def load_env() -> None:
    load_dotenv()


def get_required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value


def is_force_extract_enabled() -> bool:
    value = os.getenv("PLANZ_FORCE_EXTRACT", "")
    return value.strip().lower() in {"true", "1", "yes"}
