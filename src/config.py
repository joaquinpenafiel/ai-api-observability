from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "API Integration Lab"
    app_version: str = "0.3.0"

    log_level: str = "INFO"

    github_api_base: str = "https://api.github.com"
    github_timeout_seconds: float = 5.0
    github_max_retries: int = 2
    github_backoff_seconds: float = 0.5
    github_token: str | None = None

    anthropic_api_base: str = "https://api.anthropic.com"
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-4-6"
    anthropic_timeout_seconds: float = 15.0
    anthropic_max_retries: int = 2
    anthropic_backoff_seconds: float = 0.5
    anthropic_max_tokens: int = 300

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()
