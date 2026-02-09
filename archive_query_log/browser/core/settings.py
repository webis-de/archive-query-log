from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    es_host: str = "https://elasticsearch.example.com:9200"
    es_api_key: str | None = None
    es_verify: bool = False


settings = Settings()
