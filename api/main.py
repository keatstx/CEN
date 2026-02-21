from fastapi import FastAPI, HTTPException

from core.aop_parser import parse_aop_json
from core.engine import WorkflowEngine
from core.models import AOPDefinition, WorkflowInput, WorkflowResult
from local_llm.tlm import tlm

app = FastAPI(
    title="CEN AI Concierge",
    description="Community Equity Navigators — AOP/DAG Business Logic MVP",
    version="0.1.0",
)

# In-memory registry of loaded modules
engines: dict[str, WorkflowEngine] = {}


@app.on_event("startup")
def load_default_modules():
    """Load bundled AOP modules on startup."""
    from core.aop_parser import load_aop_from_file
    from pathlib import Path

    modules_dir = Path(__file__).resolve().parent.parent / "modules"
    for aop_file in modules_dir.glob("*.json"):
        try:
            aop = load_aop_from_file(aop_file)
            engine = WorkflowEngine()
            engine.load_aop(aop)
            engines[aop.module_name] = engine
            print(f"[Startup] Loaded module: {aop.module_name}")
        except Exception as e:
            print(f"[Startup] Failed to load {aop_file.name}: {e}")


@app.post("/execute", response_model=WorkflowResult)
def execute_workflow(payload: WorkflowInput):
    engine = engines.get(payload.module_name)
    if engine is None:
        raise HTTPException(
            status_code=404,
            detail=f"Module '{payload.module_name}' not found. "
            f"Available: {list(engines.keys())}",
        )
    return engine.execute(payload)


@app.post("/update-aop", response_model=dict)
def update_aop(aop: AOPDefinition):
    engine = WorkflowEngine()
    try:
        engine.load_aop(aop)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    engines[aop.module_name] = engine
    return {
        "status": "ok",
        "module": aop.module_name,
        "nodes": len(aop.nodes),
        "edges": len(aop.edges),
    }


@app.post("/tlm/generate")
def tlm_generate(prompt: str, max_tokens: int = 128):
    return {"response": tlm.generate(prompt, max_tokens)}
