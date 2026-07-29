from functools import lru_cache

from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls,
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        # The app's .env is the source of truth. Rank it ABOVE the process
        # environment so an unrelated ambient ANTHROPIC_API_KEY / ANTHROPIC_BASE_URL
        # (e.g. from another tool in the same shell) can't hijack our config.
        return (init_settings, dotenv_settings, env_settings, file_secret_settings)

    database_url: str
    # LLM gateway: an OpenAI-compatible endpoint (aicredits.in) serving a Claude
    # model. The model string carries the gateway's "anthropic/" prefix.
    llm_api_key: str = ""
    llm_base_url: str = "https://aicredits.in/v1"
    llm_model: str = "anthropic/claude-haiku-4.5"
    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7  # one week


@lru_cache
def get_settings() -> Settings:
    return Settings()
