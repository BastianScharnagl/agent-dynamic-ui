import json

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from agent.loop import insert_tool, run_agent_turn, select_tools
from database import init_db

app = FastAPI(title="AG-UI & A2UI Demo Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def on_startup():
    init_db()

    tools = select_tools(only_active=False)
    if not any(tool["name"] == "get_current_weather" for tool in tools):
        insert_tool(
            name="get_current_weather",
            description="Ruft die aktuellen Wetterdaten für eine bestimmte Location ab.",
            parameters_json=json.dumps({
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "Die Location für die Wetterdaten",
                    },
                },
                "required": ["location"],
            }),
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