from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    database_url_sync: str
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_access_minutes: int = 30
    jwt_refresh_days: int = 7

    google_client_id: str
    google_client_secret: str
    google_redirect_uri: str

    microsoft_client_id: str
    microsoft_client_secret: str
    microsoft_redirect_uri: str

    stripe_secret_key: str
    stripe_webhook_secret: str
    stripe_price_basic: str
    stripe_price_pro: str
    stripe_price_enterprise: str

    encryption_key: str

    embedding_model: str = "all-MiniLM-L6-v2"
    app_url: str = "http://localhost:8000"
    env: str = "development"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
