from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://prnu:prnu@localhost:5432/prnu"
    redis_url: str = "redis://localhost:6379/0"
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "prnuadmin"
    minio_secret_key: str = "prnupassword"
    minio_secure: bool = False
    prnu_image_bucket: str = "prnu-images"
    prnu_artifact_bucket: str = "prnu-artifacts"
    pce_threshold: float = 60.0
    prnu_image_size: int = 1024
    cors_allow_origins: str = "http://localhost:3000"

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allow_origins.split(",") if origin.strip()]

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
