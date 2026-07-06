from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Valor usado pelo docker-compose; pode ser sobrescrito por DATABASE_URL.
    database_url: str = (
        "postgresql+psycopg://dot_interview:dot_interview_password@postgres:5432/dot_interview"
    )

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    # Evita reler variaveis de ambiente sempre que a app precisar de configuracoes.
    return Settings()
