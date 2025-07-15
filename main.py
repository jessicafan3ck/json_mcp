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

@app.post("/run")
async def run_rpc(req: RPCRequest):
    payload = req.dict()
    # delegate to your MCP server
    result = await server.handle_mcp_request(payload)
    return result

@app.get("/healthz")
def health():
    return {"status": "ok"}
