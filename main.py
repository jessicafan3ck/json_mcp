# main.py

import asyncio
from typing import Any, Dict, List

from fastapi import FastAPI
from pydantic import BaseModel

from code_execution import CodeExecutionMCPServer

# 1) Define your Pydantic models up front

class ArtifactModel(BaseModel):
    id: str
    type: str
    meta: Dict[str, Any]

class ExecuteResponse(BaseModel):
    status: str                  # "success" or "error"
    outputs: Dict[str, Any]      # raw handler payload, e.g. {"tools": [...]}
    artifacts: List[ArtifactModel]

class RPCRequest(BaseModel):
    method: str
    params: Dict[str, Any] = {}

# 2) Instantiate FastAPI and your server

app = FastAPI(
    openapi_url="/openapi.json",
    docs_url="/docs",
    redoc_url=None
)
server = CodeExecutionMCPServer()

# 3) Your JSON‑RPC endpoint with response_model

@app.post("/run", response_model=ExecuteResponse)
async def run_rpc(req: RPCRequest):
    raw = await server.handle_mcp_request(req.dict())
    return ExecuteResponse(
        status="success",
        outputs=raw,
        artifacts=[]
    )

# 4) Healthcheck & misc routes

@app.get("/healthz")
def health():
    return {"status": "ok"}

@app.get("/")
async def read_root():
    return {"message": "JSON‑RPC service is running."}

@app.get("/favicon.ico")
async def favicon():
    return {}
