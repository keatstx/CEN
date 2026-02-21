Prompt:
"I need to build an MVP for the CEN AI Concierge Platform.

Core Architecture:

DAG Engine: Use networkx to create a WorkflowEngine class. It must support nodes of type: ACTION, CONDITION, and HANDOFF.

AOP Parser: Create a utility that takes a JSON definition (AOP) and hydrates the DAG.

Local Inference: Set up a mock interface for a 'Tiny Language Model' (TLM) that uses a local FastAPI endpoint to simulate quantized model responses.

Module Implementation: Scaffold the 'Charity Care Navigator' module with a logic branch: if income < 200% FPL, route to 'Auto-App', else route to 'Debt Cancellation Engine'.

Task:

Initialize a Python FastAPI backend.

Create /execute and /update-aop endpoints.

Implement the WorkflowEngine logic with topological sort to ensure nodes execute in order.

Create a models.py using Pydantic for the AOP JSON schema.

Start by creating the project structure and the models.py file."