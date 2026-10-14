"""Application configuration and environment settings for DataQuery AI."""

from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    """Central configuration for DataQuery AI."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    DATABASE_URL: str = Field(
        default="postgresql+psycopg://postgres:postgres@localhost:5432/app_db",
        description="PostgreSQL connection string with psycopg driver",
    )

    GOOGLE_API_KEY: str = Field(
        default="",
        description="Google Gemini API Key",
    )
    GEMINI_MODEL: str = Field(
        default="google:gemini-1.5-flash",
        description="Gemini model identifier for PydanticAI (e.g. google:gemini-1.5-flash or google:gemini-2.0-flash)",
    )

    MAX_QUERY_ROWS: int = Field(
        default=500,
        description="Hard maximum number of rows returned by any query",
    )
    QUERY_TIMEOUT_SECONDS: int = Field(
        default=10,
        description="Maximum execution timeout in seconds for PostgreSQL queries",
    )
    MAX_SQL_LENGTH: int = Field(
        default=10000,
        description="Maximum character length of SQL allowed for validation/execution",
    )
    MAX_SCHEMA_TABLES: int = Field(
        default=20,
        description="Maximum tables to inject into prompt context",
    )
    MAX_SAMPLE_ROWS: int = Field(
        default=20,
        description="Maximum sample rows returned by get_table_sample tool",
    )

    MCP_SERVER_NAME: str = Field(
        default="dataquery-mcp-server",
        description="Name of the MCP server",
    )
    MCP_SERVER_URL: str = Field(
        default="http://localhost:8001",
        description="URL for MCP server if running HTTP/SSE transport",
    )
    ENABLE_EXPLAIN: bool = Field(
        default=True,
        description="Whether EXPLAIN (read-only plan, no ANALYZE) is enabled",
    )

    API_HOST: str = Field(default="0.0.0.0", description="FastAPI host")
    API_PORT: int = Field(default=8000, description="FastAPI port")
    LOG_LEVEL: str = Field(default="INFO", description="Application log level")

    def safe_dict(self) -> dict:
        """Return non-sensitive settings for health checks and observability."""
        return {
            "gemini_model": self.GEMINI_MODEL,
            "max_query_rows": self.MAX_QUERY_ROWS,
            "query_timeout_seconds": self.QUERY_TIMEOUT_SECONDS,
            "max_sql_length": self.MAX_SQL_LENGTH,
            "max_schema_tables": self.MAX_SCHEMA_TABLES,
            "max_sample_rows": self.MAX_SAMPLE_ROWS,
            "enable_explain": self.ENABLE_EXPLAIN,
            "log_level": self.LOG_LEVEL,
            "api_port": self.API_PORT,
        }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached application settings singleton."""
    return Settings()
