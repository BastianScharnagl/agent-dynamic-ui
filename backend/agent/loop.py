# In backend/agent/loop.py

import json
import uuid
from typing import AsyncGenerator
from google import genai
from google.genai import types
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from models import Invoice
from agent.tools import UI_TOOL

client = genai.Client()

SYSTEM_INSTRUCTION = """
Du bist ein autonomer ERP-Assistent für Rechnungsverarbeitung.
1. Wenn Daten fehlen: Nutze 'fetch_invoice_data'.
2. Wenn eine Nutzerinteraktion nötig ist: Nutze 'render_custom_gui'.
3. Wenn der Nutzer Daten über die UI eingereicht hat (Tool-Response von 'render_custom_gui'):
   - Werte die übermittelten Felder aus.
   - Wenn 'confirm_approval' wahr ist oder die Entscheidung positiv war, rufe 'update_invoice_status' auf, um die Daten persistent in PostgreSQL zu speichern.
   - Erzeuge anschließend eine prägnante, freundliche Erfolgsbestätigung als Text für den Nutzer.
"""

# In-Memory-Speicher für aktive Chats (pro Session-ID)
ACTIVE_CHATS: dict[str, any] = {}

async def run_agent_turn(
    session_id: str,
    user_input: str | None,
    tool_response: dict | None,
    db: AsyncSession
) -> AsyncGenerator[str, None]:

    # 1. Backend-Tool (Read)
    async def fetch_invoice_data(invoice_id: str) -> dict:
        stmt = select(Invoice).where(Invoice.id == invoice_id)
        res = await db.execute(stmt)
        inv = res.scalar_one_or_none()
        if not inv:
            return {"error": "Rechnung nicht gefunden"}
        return {
            "invoice_id": inv.id,
            "recipient": inv.recipient,
            "total_amount": inv.total_amount,
            "status": inv.status,
            "items": inv.items
        }
    async def create_invoice(
        invoice_id: str,
        recipient: str,
        total_amount: str,
        item_description: str | None = "Standardposition"
    ) -> dict:
        """Erstellt einen neuen Rechnungseintrag in der PostgreSQL-Datenbank."""
        new_inv = Invoice(
            id=invoice_id,
            recipient=recipient,
            total_amount=f"{total_amount} EUR",
            status="pending_approval",
            items=[{"text": item_description, "amount": float(total_amount)}]
        )
        db.add(new_inv)
        await db.commit()
        return {"success": True, "created_id": invoice_id}

    # 2. Backend-Tool (Write)
    async def update_invoice_status(
        invoice_id: str,
        new_status: str,
        approved_amount: float | None = None,
        cost_center: str | None = None,
        approval_date: str | None = None,
        notes: str | None = None
    ) -> dict:
        stmt = (
            update(Invoice)
            .where(Invoice.id == invoice_id)
            .values(
                status=new_status,
                approved_amount=approved_amount,
                cost_center=cost_center,
                approval_date=approval_date,
                approval_notes=notes
            )
        )
        await db.execute(stmt)
        await db.commit()
        return {"success": True, "invoice_id": invoice_id, "status": new_status}

    # 3. Chat wiederverwenden oder neu erstellen
    if session_id not in ACTIVE_CHATS:
        ACTIVE_CHATS[session_id] = client.chats.create(
            model="gemini-3.8-flash",
            config=types.GenerateContentConfig(
                tools=[fetch_invoice_data, update_invoice_status, create_invoice, UI_TOOL],
                system_instruction=SYSTEM_INSTRUCTION
            )
        )
    
    chat = ACTIVE_CHATS[session_id]

    yield f"event: RUN_STARTED\ndata: {json.dumps({'sessionId': session_id})}\n\n"

    # Input formatieren
    if tool_response:
        yield f"event: STATUS_UPDATE\ndata: {json.dumps({'status': 'processing_user_input'})}\n\n"
        message = types.Part.from_function_response(
            name=tool_response["toolName"],
            response={"result": tool_response["output"]}
        )
    else:
        message = user_input

    # Anfrage an bestehenden Chat absenden
    response = chat.send_message(message)

    # Tool Execution Loop
    while response.function_calls:
        call = response.function_calls[0]
        call_id = str(uuid.uuid4())

        if call.name == "fetch_invoice_data":
            yield f"event: STATUS_UPDATE\ndata: {json.dumps({'status': 'reading_database'})}\n\n"
            db_data = await fetch_invoice_data(**call.args)
            response = chat.send_message(
                types.Part.from_function_response(name=call.name, response={"result": db_data})
            )

        elif call.name == "update_invoice_status":
            yield f"event: STATUS_UPDATE\ndata: {json.dumps({'status': 'persisting_approval'})}\n\n"
            mutation_res = await update_invoice_status(**call.args)
            response = chat.send_message(
                types.Part.from_function_response(name=call.name, response={"result": mutation_res})
            )

        elif call.name in ["render_custom_gui", "render_ui_component"]:
            payload = {
                "callId": call_id,
                "toolName": call.name,
                "component": call.args
            }
            yield f"event: UI_RENDER\ndata: {json.dumps(payload)}\n\n"
            break
        elif call.name == "create_invoice":
            yield f"event: STATUS_UPDATE\ndata: {json.dumps({'status': 'creating_invoice'})}\n\n"
            create_res = await create_invoice(**call.args)
            response = chat.send_message(
                types.Part.from_function_response(name=call.name, response={"result": create_res})
            )

        else:
            break

    # Textnachricht streamen
    if not response.function_calls:
        try:
            if response.text:
                yield f"event: TEXT_MESSAGE\ndata: {json.dumps({'text': response.text})}\n\n"
        except Exception:
            pass

    yield f"event: RUN_COMPLETED\ndata: {json.dumps({'sessionId': session_id})}\n\n"