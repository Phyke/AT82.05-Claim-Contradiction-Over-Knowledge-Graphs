from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: SecretStr
    openai_api_key: SecretStr
    anthropic_api_key: SecretStr
    # 1:1 with MODEL_PRICING below.
    llm_model_openai_gpt_5_4: str = "gpt-5.4"
    llm_model_openai_gpt_5_4_mini: str = "gpt-5.4-mini"
    llm_model_anthropic_opus_4_7: str = "claude-opus-4-7"
    llm_model_anthropic_sonnet_4_6: str = "claude-sonnet-4-6"
    llm_model_anthropic_haiku_4_5: str = "claude-haiku-4-5"

    # Active model for the triple-extraction notebooks. Override via .env
    # (LLM_MODEL_EXTRACTION=...) at run time to switch without code edits.
    llm_model_extraction: str = "claude-opus-4-7"


settings = Settings()


# Per-million-token API pricing (USD) used by cost estimation scripts.
# tokenizer_factor multiplies o200k_base token counts when the target model
# uses a different tokenizer family. Anthropic warns Opus 4.7's new tokenizer
# can produce up to 35% more tokens for the same text.
MODEL_PRICING: dict[str, dict[str, float]] = {
    "gpt-5.4": {"input_per_m": 2.50, "output_per_m": 15.00, "tokenizer_factor": 1.0},
    "gpt-5.4-mini": {"input_per_m": 0.75, "output_per_m": 4.50, "tokenizer_factor": 1.0},
    "claude-opus-4-7": {"input_per_m": 5.00, "output_per_m": 25.00, "tokenizer_factor": 1.35},
    "claude-sonnet-4-6": {"input_per_m": 3.00, "output_per_m": 15.00, "tokenizer_factor": 1.0},
    "claude-haiku-4-5": {"input_per_m": 1.00, "output_per_m": 5.00, "tokenizer_factor": 1.0},
}
