"""Mock Tiny Language Model — rule-based responses for MVP / fallback."""

from __future__ import annotations


class MockLanguageModel:
    """Hardcoded rule-based LLM stand-in. Always available."""

    @property
    def backend_name(self) -> str:
        return "mock-tlm-v1"

    async def generate(self, prompt: str, max_tokens: int = 128) -> str:
        prompt_lower = prompt.lower()

        if "fpl" in prompt_lower or "income" in prompt_lower:
            return (
                "Based on the provided income data, I recommend checking "
                "eligibility against the Federal Poverty Level guidelines."
            )
        if "bill" in prompt_lower or "charge" in prompt_lower:
            return (
                "I've identified potential billing discrepancies. "
                "Please review the itemized charges for accuracy."
            )
        if "dispute" in prompt_lower:
            return (
                "A formal dispute letter has been drafted based on "
                "the identified billing errors."
            )
        if "denial" in prompt_lower or "appeal" in prompt_lower:
            return (
                "The denial has been classified. An appeal letter "
                "citing relevant regulations has been drafted."
            )
        if "eligib" in prompt_lower or "medicaid" in prompt_lower:
            return (
                "Based on the household information provided, "
                "preliminary eligibility screening is complete."
            )
        if "resource" in prompt_lower or "housing" in prompt_lower or "food" in prompt_lower:
            return (
                "Community resources matching the identified needs "
                "have been compiled for navigator review."
            )

        return f"Processed request: {prompt[:80]}"

    async def is_available(self) -> bool:
        return True
