from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    ENV: str = "development"
    DATABASE_URL: str = "sqlite:///./data/planz.db"
    GOOGLE_CALENDAR_ID: str = "primary"
    GOOGLE_TOKEN_PATH: str = "./token.json"
    GOOGLE_CREDENTIALS_PATH: str = "./credentials.json"
    ICS_FEED_TOKEN: str = ""  # empty = public feed; set to require ?token=<value>
    SECRET_KEY: str = "change-me-in-production"


settings = Settings()
