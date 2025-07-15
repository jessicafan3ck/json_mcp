# main.py
import asyncio
from fastapi import FastAPI, Request
from pydantic import BaseModel
from code_execution import CodeExecutionMCPServer

app = FastAPI()
server = CodeExecutionMCPServer()

# Define the request schema
class RPCRequest(BaseModel):
    method: str
    params: dict = {}

@app.post("/run", response_model=ExecuteResponse)
async def run_rpc(req: RPCRequest):
    raw = await server.handle_mcp_request(req.dict())
    return ExecuteResponse(
        status="success",
        outputs=raw,
        artifacts=[]
    )

@app.get("/healthz")
def health():
    return {"status": "ok"}

@app.get("/")
async def read_root():
    return {"message": "JSON‑RPC service is running."}

@app.get("/favicon.ico")
async def favicon():
    return {}

from typing import Any, Dict, List
from pydantic import BaseModel

class ArtifactModel(BaseModel):
    id: str
    type: str
    meta: Dict[str, Any]

class ExecuteResponse(BaseModel):
    status: str                  # "success" or "error"
    outputs: Dict[str, Any]      # e.g. {"tools": [...]}
    artifacts: List[ArtifactModel]
