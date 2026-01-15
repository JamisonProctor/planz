from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    ENV: str = "development"
    DATABASE_URL: str = "sqlite:///./planz.db"
    GOOGLE_CALENDAR_ID: str = "primary"
    GOOGLE_TOKEN_PATH: str = "./token.json"
    GOOGLE_CREDENTIALS_PATH: str = "./credentials.json"


settings = Settings()
