import json
import asyncio
import uuid
from typing import Any, AsyncGenerator
from google import genai
from google.genai import types
from agent.db.tools import (
    DATABASE_TOOL_DECLARATIONS,
    DATABASE_TOOL_FUNCTIONS,
    select_tools,
)
from agent.ui.tools import UI_TOOL, render_custom_gui

# ---------------------------------------------------------------------------
# Dynamic Tool Execution (Dispatcher)
# ---------------------------------------------------------------------------
def execute_dynamic_function(name: str, args: dict) -> dict:
    """Mock-Dispatcher für in der Datenbank registrierte Tools."""
    if name == "calculate_vat":
        net = float(args.get("net_amount", 0.0))
        rate = float(args.get("rate", 0.19))
        vat = net * rate
        return {"net": net, "vat": round(vat, 2), "total": round(net + vat, 2)}

    return {"error": f"Keine Implementierung für dynamisches Tool '{name}' vorhanden."}


# ---------------------------------------------------------------------------
# Agentic Loop Engine
# ---------------------------------------------------------------------------
class DatabaseToolAgent:
    def __init__(self, model_name: str = "gemini-3.8-flash", max_iterations: int = 10):
        self.client = genai.Client()
        self.model_name = model_name
        self.max_iterations = max_iterations
        self.chats: dict[str, Any] = {}
        self.crud_dispatcher = {
            **DATABASE_TOOL_FUNCTIONS,
            "render_custom_gui": render_custom_gui,
        }

    def _create_chat(self):
        return self.client.chats.create(
            model=self.model_name,
            config=types.GenerateContentConfig(
                tools=self._compile_tools(),
                temperature=0.0,
            ),
        )

    def _compile_tools(self) -> list:
        """Erzeugt ausschließlich deklarative Tool-Schemas für Gemini."""
        declarations = list(DATABASE_TOOL_DECLARATIONS)
        db_records = select_tools(only_active=True)

        for record in db_records:
            parameters = record["parameters"]
            if isinstance(parameters, str):
                parameters = json.loads(parameters)

            declarations.append(
                types.FunctionDeclaration(
                    name=record["name"],
                    description=record["description"],
                    parameters=parameters,
                )
            )

        return [
            types.Tool(function_declarations=declarations),
            UI_TOOL,
        ]

    async def run_agent_turn(
        self,
        session_id: str,
        user_input: str | None,
        tool_response: dict | None,
    ) -> AsyncGenerator[str, None]:
        if session_id not in self.chats:
            self.chats[session_id] = await asyncio.to_thread(self._create_chat)
        chat = self.chats[session_id]

        yield f"event: RUN_STARTED\ndata: {json.dumps({'sessionId': session_id})}\n\n"

        if tool_response is not None:
            tool_name = tool_response.get("toolName")
            output = tool_response.get("output")
            if not tool_name or output is None:
                raise ValueError("toolResponse must include toolName and output")
            yield f"event: STATUS_UPDATE\ndata: {json.dumps({'status': 'processing_user_input'})}\n\n"
            message = types.Part.from_function_response(
                name=tool_name,
                response={"result": output},
            )
        elif user_input:
            message = user_input
        else:
            raise ValueError("Either prompt or toolResponse must be provided")

        response = await asyncio.to_thread(chat.send_message, message)
        iteration = 0
        while response.function_calls:
            iteration += 1
            if iteration > self.max_iterations:
                raise RuntimeError("Maximum agent iterations exceeded")

            call = response.function_calls[0]
            function_name = call.name
            function_args = dict(call.args) if call.args else {}

            if function_name == "render_custom_gui":
                component = render_custom_gui(**function_args)
                ui_payload = {
                    "callId": str(uuid.uuid4()),
                    "toolName": function_name,
                    "component": component,
                }
                yield f"event: UI_RENDER\ndata: {json.dumps(ui_payload)}\n\n"
                break

            if function_name in self.crud_dispatcher:
                result = await asyncio.to_thread(
                    self.crud_dispatcher[function_name], **function_args
                )
            else:
                result = execute_dynamic_function(function_name, function_args)

            response_part = types.Part.from_function_response(
                name=function_name,
                response={"result": result},
            )
            response = await asyncio.to_thread(chat.send_message, response_part)

        if not response.function_calls and response.text:
            yield f"event: TEXT_MESSAGE\ndata: {json.dumps({'text': response.text})}\n\n"

        yield f"event: RUN_COMPLETED\ndata: {json.dumps({'sessionId': session_id})}\n\n"


_agent: DatabaseToolAgent | None = None


async def run_agent_turn(
    session_id: str,
    user_input: str | None,
    tool_response: dict | None,
) -> AsyncGenerator[str, None]:
    global _agent
    if _agent is None:
        _agent = DatabaseToolAgent()

    async for event in _agent.run_agent_turn(session_id, user_input, tool_response):
        yield event