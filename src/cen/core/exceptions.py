"""Domain exceptions for the CEN engine."""

from __future__ import annotations


class CENError(Exception):
    """Base exception for all CEN domain errors."""


class ModuleNotFoundError(CENError):
    """Raised when a requested AOP module is not registered."""

    def __init__(self, module_name: str, available: list[str] | None = None):
        self.module_name = module_name
        self.available = available or []
        super().__init__(
            f"Module '{module_name}' not found. Available: {self.available}"
        )


class CycleDetectedError(CENError):
    """Raised when an AOP definition contains a cycle."""

    def __init__(self):
        super().__init__("AOP contains a cycle — circular logic paths are not allowed.")


class LLMUnavailableError(CENError):
    """Raised when the LLM backend is unreachable and no fallback succeeds."""
