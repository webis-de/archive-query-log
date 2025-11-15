from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    es_host: str = "https://elasticsearch.example.com:9200"
    es_api_key: str | None = None
    es_verify: bool = False

    class Config:
        env_file = ".env"


settings = Settings()
