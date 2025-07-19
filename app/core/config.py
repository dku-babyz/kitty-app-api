from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    AI_SERVER_URL: str = "http://220.149.244.87:8000"

    model_config = SettingsConfigDict(env_file=".env")

settings = Settings()