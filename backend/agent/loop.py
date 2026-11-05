import json
import asyncio
import uuid
import re
from typing import Any, AsyncGenerator, Dict, List
from google import genai
from google.genai import types
from agent.tools import UI_TOOL, render_custom_gui
from database import get_db_connection
from psycopg2 import sql


# ---------------------------------------------------------------------------
# CRUD-Funktionen für die Tool-Tabelle
# ---------------------------------------------------------------------------
def select_tools(only_active: bool = True) -> List[Dict[str, Any]]:
    """Liest Funktionsdefinitionen aus PostgreSQL."""
    query = "SELECT name, description, parameters, is_active FROM tools"
    if only_active:
        query += " WHERE is_active = TRUE"

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            return [dict(row) for row in cur.fetchall()]


def insert_tool(name: str, description: str, parameters_json: str) -> str:
    """Legt ein neues Tool im JSON-Schema-Format in der DB an."""
    try:
        parsed_params = json.loads(parameters_json)
    except json.JSONDecodeError as err:
        return f"Fehler beim Parsen von parameters_json: {err}"

    query = """
    INSERT INTO tools (name, description, parameters, is_active)
    VALUES (%s, %s, %s, TRUE)
    ON CONFLICT (name) DO UPDATE
    SET description = EXCLUDED.description, parameters = EXCLUDED.parameters, is_active = TRUE;
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (name, description, json.dumps(parsed_params)))
            conn.commit()
    return f"Tool '{name}' erfolgreich in der Datenbank angelegt/aktualisiert."


def update_tool(
    name: str,
    description: str = None,
    parameters_json: str = None,
    is_active: bool = None,
) -> str:
    """Aktualisiert bestehende Spalten eines Tools."""
    updates, values = [], []

    if description is not None:
        updates.append("description = %s")
        values.append(description)

    if parameters_json is not None:
        try:
            parsed = json.loads(parameters_json)
            updates.append("parameters = %s")
            values.append(json.dumps(parsed))
        except json.JSONDecodeError as err:
            return f"Fehler im JSON-Format: {err}"

    if is_active is not None:
        updates.append("is_active = %s")
        values.append(is_active)

    if not updates:
        return "Keine Änderungen übergeben."

    values.append(name)
    query = f"UPDATE tools SET {', '.join(updates)} WHERE name = %s"

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, tuple(values))
            if cur.rowcount == 0:
                return f"Tool '{name}' wurde nicht gefunden."
            conn.commit()

    return f"Tool '{name}' erfolgreich aktualisiert."


def delete_tool(name: str) -> str:
    """Entfernt ein Tool aus der Datenbank."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM tools WHERE name = %s", (name,))
            if cur.rowcount == 0:
                return f"Tool '{name}' existiert nicht."
            conn.commit()
    return f"Tool '{name}' erfolgreich gelöscht."

# Data Definition Commands
def create_table(table_name: str, columns: List[str]) -> dict:
    """Erstellt eine Tabelle mit TEXT-Spalten, deren Namen in columns angegeben sind."""
    identifier_pattern = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
    if not identifier_pattern.fullmatch(table_name):
        raise ValueError(f"Ungültiger Tabellenname: {table_name}")
    if not columns:
        raise ValueError("Mindestens eine Spalte muss angegeben werden")
    if any(not identifier_pattern.fullmatch(column) for column in columns):
        raise ValueError("Spaltennamen dürfen nur Buchstaben, Ziffern und _ enthalten")
    if len(set(columns)) != len(columns):
        raise ValueError("Spaltennamen müssen eindeutig sein")

    column_definitions = sql.SQL(", ").join(
        sql.SQL("{} TEXT").format(sql.Identifier(column))
        for column in columns
    )
    query = sql.SQL("CREATE TABLE IF NOT EXISTS {} ({})").format(
        sql.Identifier(table_name),
        column_definitions,
    )

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            print(f"Creating table {table_name} with columns: {columns}")
            cur.execute(query)
            conn.commit()
    return {"success": True, "table_name": table_name, "columns": columns}

def alter_table_add_column(table_name: str, column_definition: str) -> None:
    """Fügt einer bestehenden Tabelle eine neue Spalte hinzu."""
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            print(f"Altering table {table_name} to add column: {column_definition}")
            cur.execute(
                f"ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS {column_definition}"
            )
            conn.commit()

def select(table_name: str, columns: List[str] = None, where_clause: str = None) -> List[Dict[str, Any]]:
    """Liest Daten aus einer Tabelle."""
    columns_str = ", ".join(columns) if columns else "*"
    query = f"SELECT {columns_str} FROM {table_name}"
    if where_clause:
        query += f" WHERE {where_clause}"

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            print(f"Executing query: {query}")
            cur.execute(query)
            return [dict(row) for row in cur.fetchall()]

def insert(table_name: str, data: Dict[str, Any]) -> None:
    """Fügt einen neuen Datensatz in eine Tabelle ein."""
    columns = ", ".join(data.keys())
    placeholders = ", ".join(["%s"] * len(data))
    query = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            print(f"Inserting into {table_name}: {data}")
            cur.execute(query, tuple(data.values()))
            conn.commit()

def update(table_name: str, data: Dict[str, Any], where_clause: str) -> None:
    """Aktualisiert bestehende Datensätze in einer Tabelle."""
    set_clause = ", ".join([f"{key} = %s" for key in data.keys()])
    query = f"UPDATE {table_name} SET {set_clause} WHERE {where_clause}"

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            print(f"Updating {table_name} with data: {data}, where: {where_clause}")
            cur.execute(query, tuple(data.values()))
            conn.commit()

def delete(table_name: str, where_clause: str) -> None:
    """Löscht Datensätze aus einer Tabelle."""
    query = f"DELETE FROM {table_name} WHERE {where_clause}"

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            conn.commit()


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
            "select_tools": select_tools,
            "insert_tool": insert_tool,
            "update_tool": update_tool,
            "delete_tool": delete_tool,
            "render_custom_gui": render_custom_gui,
            "select": select,
            "insert": insert,
            "update": update,
            "delete": delete,
            "create_table": create_table,
            "alter_table_add_column": alter_table_add_column,
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
        """Erzeugt die aktuelle Liste an Tools aus Python-Funktionen und DB-Einträgen."""
        tools = [select_tools, insert_tool, update_tool, delete_tool, select, insert, update, delete, create_table, alter_table_add_column, UI_TOOL]

        db_records = select_tools(only_active=True)

        function_declarations = []

        for record in db_records:
            parameters = record["parameters"]

            # JSON-String in Python-Dictionary umwandeln
            if isinstance(parameters, str):
                parameters = json.loads(parameters)

            function_declarations.append(
                types.FunctionDeclaration(
                    name=record["name"],
                    description=record["description"],
                    parameters=parameters,
                )
            )

        if function_declarations:
            tools.append(
                types.Tool(function_declarations=function_declarations)
            )

        return tools

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
            call_id = str(uuid.uuid4())
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

            if call.name in ["render_custom_gui"]:
                payload = {
                    "callId": call_id,
                    "toolName": call.name,
                    "component": call.args
                }
                yield f"event: UI_RENDER\ndata: {json.dumps(payload)}\n\n"
                break
            else:
                break

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