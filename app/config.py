from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Valor usado pelo docker-compose; pode ser sobrescrito por DATABASE_URL.
    database_url: str = (
        "postgresql+psycopg://dot_interview:dot_interview_password@postgres:5432/dot_interview"
    )
    # Token simples para proteger endpoints administrativos do MVP.
    api_token: str = "dev-api-token"
    # Modelo usado pelo agente LangChain. Pode ser trocado sem alterar codigo.
    langchain_model: str = "openai:tencent/hy3:free"
    # Timeout maximo para chamadas do agente, em segundos.
    conversation_agent_timeout_seconds: float = 180.0
    # Identificacao enviada em requisicoes feitas pelas ferramentas do agente.
    conversation_agent_name: str = "DOT-Interview-Tutor-MVP"
    conversation_agent_version: str = "1.0"
    # Origens locais permitidas para o frontend Vite em desenvolvimento.
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    # Evita reler variaveis de ambiente sempre que a app precisar de configuracoes.
    return Settings()
