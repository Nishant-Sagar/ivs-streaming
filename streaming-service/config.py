from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Amazon IVS — leave blank to run in mock (camera) mode
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    aws_region: str = "us-east-1"

    # JWT / auth
    secret_key: str = "change-this-in-production"
    algorithm: str = "HS256"

    cors_origins: str = "*"

    @property
    def ivs_enabled(self) -> bool:
        return bool(self.aws_access_key_id and self.aws_secret_access_key)

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
