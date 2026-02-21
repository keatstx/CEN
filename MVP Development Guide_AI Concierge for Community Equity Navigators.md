# 🛠 CEN AI Concierge: MVP Development Guide

This guide outlines the steps to build the Layer 2 (AOP/DAG) Business Logic MVP.

---

## 🏗 Project Structure
* `/core`: The DAG Engine and AOP Parser logic.
* `/modules`: AOP JSON definitions for the 5 core assistants.
* `/api`: FastAPI routes for the mobile UX to trigger workflows.
* `/local_llm`: Scripts to manage the quantized GGUF models via `llama-cpp-python`.

---

## 🚀 Step-by-Step Build Instructions

### Phase 1: The "Brain" (DAG Engine)
The engine must translate AOP instructions into a Directed Acyclic Graph.
1. **Define the Schema:** Use Pydantic to enforce that every node has an `id`, `type`, and `metadata`.
2. **Implement Topological Sort:** Use `networkx.topological_sort` to ensure that "Income Verification" always happens before "Program Matching."

### Phase 2: The Modules (AOP JSONs)
Create the logic for the five core modules. Example logic for the **Debt Cancellation Engine**:
* **Input:** Image/PDF of medical bill.
* **Nodes:** * `Audit_Duplicate`: Checks for double charges.
    * `Audit_NSA`: Checks for No Surprises Act violations.
    * `Output_Letter`: Generates a dispute PDF.

### Phase 3: Edge Privacy (TLM Integration)
To ensure the "Privacy by Design" requirement:
1. **Quantization:** Download a `Phi-3-mini-4k-instruct-q4.gguf`.
2. **Local Server:** Wrap the model in a local API so the DAG engine can call "The AI" without data leaving the environment.

### Phase 4: The FIC Sync (TDT Prototype)
1. **State Capture:** Create a "Telemetry" function that triggers after every DAG execution.
2. **Anonymization:** Ensure the function strips PII (Names, SSNs) and only sends: `{ "module": "charity_care", "outcome": "eligible", "latency": "1.2s" }`.

---

## ⚠️ Critical Success Factors
* **No Loops:** The DAG engine must throw an error if a business analyst accidentally creates a circular logic path.
* **Graceful Degradation:** If the Local LLM is too slow, the system should have a "Hardcoded Rule" fallback for basic FPL calculations.

---

## 🛠 Commands to Run
```bash
# Install dependencies
pip install fastapi uvicorn networkx pydantic llama-cpp-python

# Run the dev server
uvicorn api.main:app --reload