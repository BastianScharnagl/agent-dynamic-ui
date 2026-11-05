import os
from contextlib import contextmanager
from typing import Generator

import psycopg2
from psycopg2.extras import RealDictCursor

from models import SCHEMA_STATEMENTS
from urllib.parse import urlparse

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/agent_db")
parsed = urlparse(DATABASE_URL)

print(f"Connecting as user: {parsed.username}")
print(f"Connecting to database: {parsed.path.lstrip('/')}")


@contextmanager
def get_db_connection() -> Generator[psycopg2.extensions.connection, None, None]:
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL must be configured")

    scheme, separator, remainder = DATABASE_URL.partition("://")
    if separator and scheme.startswith("postgresql+"):
        dsn = f"postgresql://{remainder}"
    else:
        dsn = DATABASE_URL

    connection = psycopg2.connect(
        dsn,
        cursor_factory=RealDictCursor,
    )
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def init_db() -> None:
    with get_db_connection() as connection:
        with connection.cursor() as cursor:
            for statement in SCHEMA_STATEMENTS:
                print(statement)
                cursor.execute(statement)
