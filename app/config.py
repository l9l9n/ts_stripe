from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    stripe_secret_key: str
    stripe_webhook_secret: str
    base_url: str = "http://localhost:8000"
    database_url: str = "sqlite+aiosqlite:///./payments.db"

    class Config:
        env_file = ".env"


settings = Settings()
