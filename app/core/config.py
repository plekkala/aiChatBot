from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Anthropic
    anthropic_api_key: str

    # PostgreSQL
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "doc_chatbot"
    postgres_user: str = "postgres"
    postgres_password: str = "postgres"

    # App
    app_env: str = "development"
    app_port: int = 8000
    app_secret_key: str = "dev-secret"

    # Chunking
    chunk_size: int = 512
    chunk_overlap: int = 50
    top_k_results: int = 5

    # LLM
    claude_model: str = "claude-sonnet-4-6"
    max_tokens: int = 1024

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
