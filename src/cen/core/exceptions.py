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


class SessionNotFoundError(CENError):
    """Raised when a requested session does not exist."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        super().__init__(f"Session '{session_id}' not found.")


class ApprovalNotPendingError(CENError):
    """Raised when trying to approve a session not in AWAITING_APPROVAL status."""

    def __init__(self, session_id: str, current_status: str):
        self.session_id = session_id
        self.current_status = current_status
        super().__init__(
            f"Session '{session_id}' is not awaiting approval (current status: {current_status})."
        )


class LLMUnavailableError(CENError):
    """Raised when the LLM backend is unreachable and no fallback succeeds."""
