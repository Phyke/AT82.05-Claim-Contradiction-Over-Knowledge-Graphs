from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    anthropic_api_key: SecretStr
    openai_api_key: SecretStr

    llm_model_anthropic_opus_4_7: str = "claude-opus-4-7"
    llm_model_anthropic_sonnet_4_6: str = "claude-sonnet-4-6"
    llm_model_anthropic_haiku_4_5: str = "claude-haiku-4-5"
    llm_model_openai_gpt_5_4: str = "gpt-5.4"
    llm_model_openai_gpt_5_4_mini: str = "gpt-5.4-mini"

    default_model: str = "claude-sonnet-4-6"

    # Reserved for future KG integration; not used in current iteration.
    # Optional so the backend boots without Neo4j running.
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: SecretStr | None = None


settings = Settings()
