from typing import Any, Final
from uuid import UUID

import psycopg
from psycopg.rows import class_row

from project_hub.documents.entities import Document, NewDocument

_COLUMNS: Final = (
    "d.id, d.project_id, d.name, d.content_type, d.size, d.storage_key, d.uploaded_by, "
    "u.login AS uploader_login, d.created_at, d.updated_at "
)


class SqlDocumentRepository:
    def __init__(self, conn: psycopg.AsyncConnection[Any]) -> None:
        self._conn = conn

    async def add(self, document: NewDocument) -> Document:
        await self._conn.execute("SAVEPOINT add_document")
        try:
            async with self._conn.cursor(row_factory=class_row(Document)) as cur:
                await cur.execute(
                    "WITH d AS ("
                    "INSERT INTO documents "
                    "(project_id, name, content_type, size, storage_key, uploaded_by) "
                    "VALUES (%s, %s, %s, %s, %s, %s) RETURNING *"
                    ") SELECT " + _COLUMNS + "FROM d LEFT JOIN users u ON u.id = d.uploaded_by",
                    (
                        document.project_id,
                        document.name,
                        document.content_type,
                        document.size,
                        document.storage_key,
                        document.uploaded_by,
                    ),
                )
                row = await cur.fetchone()
        except psycopg.Error:
            await self._conn.execute("ROLLBACK TO SAVEPOINT add_document")
            await self._conn.execute("RELEASE SAVEPOINT add_document")
            raise
        await self._conn.execute("RELEASE SAVEPOINT add_document")
        assert row is not None
        return row

    async def get(self, document_id: UUID) -> Document | None:
        async with self._conn.cursor(row_factory=class_row(Document)) as cur:
            await cur.execute(
                "SELECT " + _COLUMNS + "FROM documents d "
                "LEFT JOIN users u ON u.id = d.uploaded_by WHERE d.id = %s",
                (document_id,),
            )
            return await cur.fetchone()
