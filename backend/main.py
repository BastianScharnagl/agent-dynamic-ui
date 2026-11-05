from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_db, engine, Base
from models import Invoice
from agent.loop import run_agent_turn

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
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Initiale Testdaten
    async with AsyncSession(engine) as session:
        inv = await session.get(Invoice, "INV-2026-99")
        if not inv:
            session.add(Invoice(
                id="INV-2026-99",
                recipient="Acme Corp GmbH",
                total_amount="1499.50 EUR",
                status="pending_approval",
                items=[{"text": "Consulting", "amount": 1000}, {"text": "Hosting", "amount": 499.5}]
            ))
            await session.commit()

class ChatRequest(BaseModel):
    sessionId: str
    prompt: str | None = None
    toolResponse: dict | None = None

@app.post("/api/agent/stream")
async def stream_agent(req: ChatRequest, db: AsyncSession = Depends(get_db)):
    print(f"Received request: sessionId={req.sessionId}, prompt={req.prompt}, toolResponse={req.toolResponse}")
    return StreamingResponse(
        run_agent_turn(req.sessionId, req.prompt, req.toolResponse, db),
        media_type="text/event-stream"
    )