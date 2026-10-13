"""Application configuration using Pydantic Settings."""


from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class BotConfig(BaseSettings):
    """Production bot configuration loaded from environment variables and .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Telegram Credentials
    bot_token: SecretStr = Field(
        ...,
        description="Telegram Bot API token obtained from @BotFather",
    )

    # NormaHub AI Gateway
    normahub_api_key: SecretStr = Field(
        ...,
        description="NormaHub API key (nr_hub_... from https://normahub.cc)",
    )
    normahub_base_url: str = Field(
        default="https://api.normahub.cc/v1",
        description="NormaHub API base URL",
    )
    default_model: str = Field(
        default="deepseek-v4.1-flash",
        description="Default LLM model identifier for completions",
    )

    # Streaming & Debouncer
    stream_debounce_interval: float = Field(
        default=0.8,
        description="Debounce delay in seconds for editing streaming Telegram messages",
        ge=0.2,
        le=5.0,
    )

    # Context Memory
    max_context_turns: int = Field(
        default=10,
        description="Maximum conversation turns (user + assistant pairs) retained in sliding window",
        ge=1,
        le=50,
    )
    system_prompt: str = Field(
        default=(
            "Ты — технический ассистент разработчика. Отвечай кратко, по существу, "
            "приводи валидные примеры кода с аннотациями типов и соблюдай архитектурные паттерны."
        ),
        description="Default system instruction for chat completions",
    )

    # Rate Limiting & Throttling
    rate_limit_per_second: float = Field(
        default=1.0,
        description="Minimum seconds allowed between user requests (throttling)",
        ge=0.1,
    )

    # Storage & Infrastructure
    database_path: str = Field(
        default="data/bot_database.db",
        description="Path to SQLite persistent database file (WAL mode)",
    )
    redis_url: str | None = Field(
        default=None,
        description="Optional Redis connection URL for FSM and state persistence (e.g. redis://redis:6379/0)",
    )


    # Administration & Observability
    admin_user_ids: list[int] = Field(
        default_factory=list,
        description="List of Telegram user IDs with administrative privileges",
    )
    log_level: str = Field(
        default="INFO",
        description="Standard logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
    )

    @field_validator("normahub_base_url")
    @classmethod
    def clean_base_url(cls, v: str) -> str:
        """Strip trailing slashes from base URL."""
        return v.rstrip("/")

    @field_validator("log_level")
    @classmethod
    def normalize_log_level(cls, v: str) -> str:
        """Ensure valid uppercase log level."""
        level = v.upper().strip()
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if level not in allowed:
            raise ValueError(f"Log level must be one of {allowed}, got {v}")
        return level

    def is_admin(self, user_id: int) -> bool:
        """Check if a Telegram user ID belongs to the configured administrators."""
        return user_id in self.admin_user_ids


def load_config() -> BotConfig:
    """Helper function to instantiate and validate BotConfig."""
    return BotConfig()  # type: ignore[call-arg]
