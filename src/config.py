import re
from functools import lru_cache

from pydantic import ConfigDict, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    openrouter_api_key: str
    mcp_access_key: str
    app_name: str = "open-brain"
    app_env: str = "development"
    log_level: str = "INFO"
    port: int = 80

    model_config = ConfigDict(env_file=".env", extra="ignore")

    @field_validator("mcp_access_key")
    @classmethod
    def validate_mcp_access_key(cls, v: str) -> str:
        if not re.fullmatch(r"[0-9a-f]{64}", v):
            raise ValueError("MCP_ACCESS_KEY must be a 64-character hex string")
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
