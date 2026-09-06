from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
import os

# Locates the 'src/.env' file relative to this config file
BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    OPENAI_API_KEY: str
    MODEL: str
    APP_NAME: str
    DB_SCHEMA: str 
    COHERE_API_KEY: str

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

def get_settings():
    settings=Settings()

    os.environ["CO_API_KEY"] = settings.COHERE_API_KEY
    return settings