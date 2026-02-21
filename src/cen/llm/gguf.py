"""GGUF language model backend via llama-cpp-python."""

from __future__ import annotations

import asyncio
from functools import partial
from pathlib import Path


class GGUFLanguageModel:
    """Wraps llama-cpp-python for local GGUF model inference.

    CPU-bound inference is offloaded to a thread via run_in_executor.
    """

    def __init__(self, model_path: str):
        self._model_path = model_path
        self._llm: object | None = None
        self._load_error: str | None = None
        self._try_load()

    def _try_load(self) -> None:
        try:
            from llama_cpp import Llama  # type: ignore[import-untyped]

            if not Path(self._model_path).exists():
                self._load_error = f"Model file not found: {self._model_path}"
                return
            self._llm = Llama(model_path=self._model_path, n_ctx=2048, verbose=False)
        except ImportError:
            self._load_error = "llama-cpp-python is not installed"
        except Exception as exc:
            self._load_error = str(exc)

    @property
    def backend_name(self) -> str:
        return "gguf"

    async def generate(self, prompt: str, max_tokens: int = 128) -> str:
        if self._llm is None:
            raise RuntimeError(self._load_error or "GGUF model not loaded")

        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None,
            partial(
                self._llm,  # type: ignore[misc]
                prompt,
                max_tokens=max_tokens,
                stop=["\n\n"],
            ),
        )
        choices = result.get("choices", [])  # type: ignore[union-attr]
        if choices:
            return choices[0].get("text", "").strip()
        return ""

    async def is_available(self) -> bool:
        return self._llm is not None
