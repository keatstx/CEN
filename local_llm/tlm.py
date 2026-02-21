"""Mock Tiny Language Model (TLM) interface.

In production this would call a local quantized GGUF model via llama-cpp-python.
For the MVP it returns hardcoded rule-based responses so the DAG engine can
function without a real model.
"""


class TinyLanguageModel:
    def __init__(self):
        self.model_name = "mock-tlm-v1"

    def generate(self, prompt: str, max_tokens: int = 128) -> str:
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

        return f"Processed request: {prompt[:80]}"


# Singleton for the app
tlm = TinyLanguageModel()
