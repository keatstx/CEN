"""Environment-based configuration via pydantic-settings."""

from __future__ import annotations

from typing import List, Literal

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = {"env_prefix": "CEN_"}

    # LLM
    llm_backend: Literal["mock", "gguf", "api"] = "mock"
    gguf_model_path: str = "./models/model.gguf"
    llm_timeout: float = 10.0
    llm_api_base: str = "http://localhost:11434/v1"
    llm_api_key: str = ""
    llm_model: str = "phi3:mini"

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

    # Uploads
    uploads_dir: str = "./data/uploads"

    # Deployment / hardening hooks (v1: synthetic data only)
    deployment_mode: Literal["synthetic", "production"] = "synthetic"
    operator_password: str = ""  # empty = auth disabled (dev/test default)
    llm_baa_confirmed: bool = False  # required for `production` mode + `api` backend

    # RBAC stub — comma-separated operator ids that have admin powers
    # (SOP-to-AOP authoring, etc.). In dev stub mode the single operator
    # is always admin. Real RBAC replaces this list.
    admin_operators: List[str] = []
