from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "API Integration Lab"
    app_version: str = "0.2.0"

    log_level: str = "INFO"

    github_api_base: str = "https://api.github.com"
    github_timeout_seconds: float = 5.0
    github_token: str | None = None

    model_config = SettingsConfigDict(
    env_file=".env",
    env_file_encoding="utf-8",
    case_sensitive=False,
    extra="ignore",
)


settings = Settings()