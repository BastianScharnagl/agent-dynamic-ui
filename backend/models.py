SCHEMA_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS tools (
        id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
        name TEXT NOT NULL,
        description TEXT,
        parameters JSONB NOT NULL,
        is_active BOOLEAN NOT NULL DEFAULT TRUE
    )
    """,
    "ALTER TABLE tools ALTER COLUMN id SET DEFAULT gen_random_uuid()::text",
    "CREATE UNIQUE INDEX IF NOT EXISTS tools_name_unique ON tools (name)",
    """
    CREATE TABLE IF NOT EXISTS chat_sessions (
        id TEXT PRIMARY KEY,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMPTZ,
        history JSONB NOT NULL DEFAULT '[]'::jsonb
    )
    """,
)
