import json
import re
from typing import Any

from google.genai import types
from psycopg2 import sql

from agent.db.database import get_db_connection

_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

_STRING = types.Schema(type="STRING")
_BOOLEAN = types.Schema(type="BOOLEAN")
_STRING_ARRAY = types.Schema(type="ARRAY", items=_STRING)
_JSON_OBJECT = types.Schema(
    type="OBJECT",
    description="JSON-Objekt mit den Spaltennamen als Schlüsseln",
)
_COLUMN_TYPE_PATTERN = re.compile(
    r"^(?:SMALLINT|INTEGER|BIGINT|TEXT|BOOLEAN|DATE|UUID|JSONB|"
    r"TIMESTAMP(?: WITH(?:OUT)? TIME ZONE)?|"
    r"VARCHAR(?:\(\d+\))?|NUMERIC(?:\(\d+(?:,\s*\d+)?\))?)$",
    re.IGNORECASE,
)


def select_tools(only_active: bool = True) -> list[dict[str, Any]]:
    query = "SELECT name, description, parameters, is_active FROM tools"
    if only_active:
        query += " WHERE is_active = TRUE"

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            return [dict(row) for row in cur.fetchall()]


def insert_tool(name: str, description: str, parameters_json: str) -> str:
    parsed_params = json.loads(parameters_json)
    query = """
    INSERT INTO tools (name, description, parameters, is_active)
    VALUES (%s, %s, %s, TRUE)
    ON CONFLICT (name) DO UPDATE
    SET description = EXCLUDED.description,
        parameters = EXCLUDED.parameters,
        is_active = TRUE
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (name, description, json.dumps(parsed_params)))
    return f"Tool '{name}' erfolgreich angelegt oder aktualisiert."


def update_tool(
    name: str,
    description: str | None = None,
    parameters_json: str | None = None,
    is_active: bool | None = None,
) -> str:
    updates = []
    values: list[Any] = []

    if description is not None:
        updates.append("description = %s")
        values.append(description)
    if parameters_json is not None:
        updates.append("parameters = %s")
        values.append(json.dumps(json.loads(parameters_json)))
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
    return f"Tool '{name}' erfolgreich aktualisiert."


def delete_tool(name: str) -> str:
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM tools WHERE name = %s", (name,))
            if cur.rowcount == 0:
                return f"Tool '{name}' wurde nicht gefunden."
    return f"Tool '{name}' erfolgreich gelöscht."


def _validate_identifier(identifier: str, label: str) -> None:
    if not _IDENTIFIER_PATTERN.fullmatch(identifier):
        raise ValueError(f"Ungültiger {label}: {identifier}")


def create_table(table_name: str, columns: list[str]) -> dict[str, Any]:
    """Erstellt eine Tabelle mit TEXT-Spalten."""
    _validate_identifier(table_name, "Tabellenname")
    if not columns:
        raise ValueError("Mindestens eine Spalte muss angegeben werden")
    for column in columns:
        _validate_identifier(column, "Spaltenname")
    if len(set(columns)) != len(columns):
        raise ValueError("Spaltennamen müssen eindeutig sein")

    definitions = sql.SQL(", ").join(
        sql.SQL("{} TEXT").format(sql.Identifier(column))
        for column in columns
    )
    query = sql.SQL("CREATE TABLE IF NOT EXISTS {} ({})").format(
        sql.Identifier(table_name),
        definitions,
    )
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query)
    return {"success": True, "table_name": table_name, "columns": columns}


def alter_table_add_column(table_name: str, column_definition: str) -> dict[str, Any]:
    _validate_identifier(table_name, "Tabellenname")
    column_name, separator, data_type = column_definition.partition(" ")
    if not separator or not data_type.strip():
        raise ValueError("column_definition muss Spaltenname und Datentyp enthalten")
    _validate_identifier(column_name, "Spaltenname")
    data_type = data_type.strip()
    if not _COLUMN_TYPE_PATTERN.fullmatch(data_type):
        raise ValueError(f"Nicht unterstützter SQL-Datentyp: {data_type}")
    query = sql.SQL("ALTER TABLE {} ADD COLUMN IF NOT EXISTS {} {}").format(
        sql.Identifier(table_name),
        sql.Identifier(column_name),
        sql.SQL(data_type),
    )
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query)
    return {"success": True, "table_name": table_name, "column": column_name}


def select(
    table_name: str,
    columns: list[str] | None = None,
    where_clause: str | None = None,
) -> list[dict[str, Any]]:
    _validate_identifier(table_name, "Tabellenname")
    selected_columns = (
        sql.SQL(", ").join(sql.Identifier(column) for column in columns)
        if columns
        else sql.SQL("*")
    )
    query = sql.SQL("SELECT {} FROM {}").format(
        selected_columns,
        sql.Identifier(table_name),
    )
    if where_clause:
        query += sql.SQL(" WHERE ") + sql.SQL(where_clause)
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            return [dict(row) for row in cur.fetchall()]


def insert(table_name: str, data: dict[str, Any]) -> dict[str, Any]:
    _validate_identifier(table_name, "Tabellenname")
    if not data:
        raise ValueError("Mindestens ein Spaltenwert muss angegeben werden")
    columns = list(data)
    for column in columns:
        _validate_identifier(column, "Spaltenname")
    query = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
        sql.Identifier(table_name),
        sql.SQL(", ").join(sql.Identifier(column) for column in columns),
        sql.SQL(", ").join(sql.Placeholder() for _ in columns),
    )
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, tuple(data[column] for column in columns))
    return {"success": True, "table_name": table_name}


def update(
    table_name: str,
    data: dict[str, Any],
    where_clause: str,
) -> dict[str, Any]:
    _validate_identifier(table_name, "Tabellenname")
    if not data:
        raise ValueError("Mindestens ein Spaltenwert muss angegeben werden")
    for column in data:
        _validate_identifier(column, "Spaltenname")
    assignments = sql.SQL(", ").join(
        sql.SQL("{} = {}").format(sql.Identifier(column), sql.Placeholder())
        for column in data
    )
    query = sql.SQL("UPDATE {} SET {} WHERE {}").format(
        sql.Identifier(table_name),
        assignments,
        sql.SQL(where_clause),
    )
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, tuple(data.values()))
    return {"success": True, "table_name": table_name}


def delete(table_name: str, where_clause: str) -> dict[str, Any]:
    _validate_identifier(table_name, "Tabellenname")
    query = sql.SQL("DELETE FROM {} WHERE {}").format(
        sql.Identifier(table_name),
        sql.SQL(where_clause),
    )
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query)
    return {"success": True, "table_name": table_name}


DATABASE_TOOL_FUNCTIONS = {
    "select_tools": select_tools,
    "insert_tool": insert_tool,
    "update_tool": update_tool,
    "delete_tool": delete_tool,
    "create_table": create_table,
    "alter_table_add_column": alter_table_add_column,
    "select": select,
    "insert": insert,
    "update": update,
    "delete": delete,
}

DATABASE_TOOL_DECLARATIONS = [
    types.FunctionDeclaration(
        name="select_tools",
        description="Listet registrierte Tools auf; optional nur aktive Tools.",
        parameters=types.Schema(
            type="OBJECT",
            properties={"only_active": _BOOLEAN},
        ),
    ),
    types.FunctionDeclaration(
        name="insert_tool",
        description="Legt eine Tooldefinition an oder aktualisiert sie.",
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "name": _STRING,
                "description": _STRING,
                "parameters_json": _STRING,
            },
            required=["name", "description", "parameters_json"],
        ),
    ),
    types.FunctionDeclaration(
        name="update_tool",
        description="Aktualisiert eine Tooldefinition anhand ihres Namens.",
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "name": _STRING,
                "description": _STRING,
                "parameters_json": _STRING,
                "is_active": _BOOLEAN,
            },
            required=["name"],
        ),
    ),
    types.FunctionDeclaration(
        name="delete_tool",
        description="Löscht eine Tooldefinition anhand ihres Namens.",
        parameters=types.Schema(
            type="OBJECT",
            properties={"name": _STRING},
            required=["name"],
        ),
    ),
    types.FunctionDeclaration(
        name="create_table",
        description="Erstellt eine Tabelle mit TEXT-Spalten.",
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "table_name": _STRING,
                "columns": _STRING_ARRAY,
            },
            required=["table_name", "columns"],
        ),
    ),
    types.FunctionDeclaration(
        name="alter_table_add_column",
        description="Fügt einer Tabelle eine Spalte hinzu. column_definition enthält Spaltenname und SQL-Datentyp.",
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "table_name": _STRING,
                "column_definition": _STRING,
            },
            required=["table_name", "column_definition"],
        ),
    ),
    types.FunctionDeclaration(
        name="select",
        description="Liest Datensätze aus einer Tabelle.",
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "table_name": _STRING,
                "columns": _STRING_ARRAY,
                "where_clause": _STRING,
            },
            required=["table_name"],
        ),
    ),
    types.FunctionDeclaration(
        name="insert",
        description="Fügt einen Datensatz in eine Tabelle ein.",
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "table_name": _STRING,
                "data": _JSON_OBJECT,
            },
            required=["table_name", "data"],
        ),
    ),
    types.FunctionDeclaration(
        name="update",
        description="Aktualisiert Datensätze einer Tabelle.",
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "table_name": _STRING,
                "data": _JSON_OBJECT,
                "where_clause": _STRING,
            },
            required=["table_name", "data", "where_clause"],
        ),
    ),
    types.FunctionDeclaration(
        name="delete",
        description="Löscht Datensätze aus einer Tabelle.",
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "table_name": _STRING,
                "where_clause": _STRING,
            },
            required=["table_name", "where_clause"],
        ),
    ),
]
