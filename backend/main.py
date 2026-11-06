import json

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from agent.db.tools import insert_tool, select_tools
from agent.loop import run_agent_turn

app = FastAPI(title="AG-UI & A2UI Demo Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    sessionId: str
    prompt: str | None = None
    toolResponse: dict | None = None

@app.post("/api/agent/stream")
async def stream_agent(req: ChatRequest):
    print(f"Received request: sessionId={req.sessionId}, prompt={req.prompt}, toolResponse={req.toolResponse}")
    return StreamingResponse(
        run_agent_turn(req.sessionId, req.prompt, req.toolResponse),
        media_type="text/event-stream"
    )