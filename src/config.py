from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache

class Settings(BaseSettings): 
    ANTHROPIC_API_KEY: str = ""
    GROQ_API_KEY: str = ""

    TASK_A_MODEL: str = ""
    TASK_B_MODEL: str = ""
    RATING_MODEL: str = ""

    PROFILE_STORE_PATH: str = ""

    model_config = SettingsConfigDict(
        env_file=".env", 
        case_sensitive=False, 
        env_file_encoding="utf-8"
    )

@lru_cache
def get_settings(): 
    return Settings()

settings = get_settings()

