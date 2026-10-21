from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application configuration settings.
    Reads values from the .env file automatically.
    """

    # LLM Settings
    ollama_host: str
    ollama_model: str
    search_model: str

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


# Instantiate the settings
settings = Settings()
