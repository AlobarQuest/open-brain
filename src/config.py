from pydantic import ConfigDict
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


settings = Settings()
