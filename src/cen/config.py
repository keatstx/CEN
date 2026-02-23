"""Environment-based configuration via pydantic-settings."""

from __future__ import annotations

from typing import List, Literal

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_prefix": "CEN_"}

    # LLM
    llm_backend: Literal["mock", "gguf"] = "mock"
    gguf_model_path: str = "./models/model.gguf"
    llm_timeout: float = 10.0

    # CORS
    cors_origins: List[str] = ["http://localhost:3000", "http://localhost:5173"]

    # Concurrency
    llm_max_concurrency: int = 2

    # Logging
    log_renderer: Literal["json", "console"] = "console"

    # Privacy
    pii_backend: Literal["regex", "presidio"] = "regex"

    # Database
    db_path: str = "./data/cen.db"
