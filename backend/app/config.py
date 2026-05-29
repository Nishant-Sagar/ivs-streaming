from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_region: str = "us-east-1"

    secret_key: str = "change-this-secret-key-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440  # 24 hours

    database_url: str = "sqlite:///./streaming.db"

    cors_origins: str = "http://localhost:8080,http://localhost:3000"

    # Pre-provisioned IVS channel — set these to skip CreateChannel on every request
    ivs_channel_arn: str = ""
    ivs_ingest_endpoint: str = ""
    ivs_stream_key: str = ""
    ivs_playback_url: str = ""

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
