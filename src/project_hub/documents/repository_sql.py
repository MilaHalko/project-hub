from typing import Any, Final
from uuid import UUID

import psycopg
from psycopg.rows import class_row

from project_hub.documents.entities import Document, NewDocument, ReplacedFile

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

    async def replace_file(self, document_id: UUID, file: ReplacedFile) -> Document | None:
        await self._conn.execute("SAVEPOINT replace_document_file")
        try:
            async with self._conn.cursor(row_factory=class_row(Document)) as cur:
                await cur.execute(
                    "WITH d AS ("
                    "UPDATE documents SET name = %s, content_type = %s, size = %s, "
                    "storage_key = %s, uploaded_by = %s, updated_at = now() "
                    "WHERE id = %s RETURNING *"
                    ") SELECT " + _COLUMNS + "FROM d LEFT JOIN users u ON u.id = d.uploaded_by",
                    (
                        file.name,
                        file.content_type,
                        file.size,
                        file.storage_key,
                        file.uploaded_by,
                        document_id,
                    ),
                )
                row = await cur.fetchone()
        except psycopg.Error:
            await self._conn.execute("ROLLBACK TO SAVEPOINT replace_document_file")
            await self._conn.execute("RELEASE SAVEPOINT replace_document_file")
            raise
        await self._conn.execute("RELEASE SAVEPOINT replace_document_file")
        return row

    async def list_for_project(self, project_id: UUID) -> list[Document]:
        async with self._conn.cursor(row_factory=class_row(Document)) as cur:
            await cur.execute(
                "SELECT " + _COLUMNS + "FROM documents d "
                "LEFT JOIN users u ON u.id = d.uploaded_by WHERE d.project_id = %s "
                "ORDER BY d.created_at DESC, d.id DESC",
                (project_id,),
            )
            return await cur.fetchall()

    async def delete(self, document_id: UUID) -> Document | None:
        async with self._conn.cursor(row_factory=class_row(Document)) as cur:
            await cur.execute(
                "WITH d AS (DELETE FROM documents WHERE id = %s RETURNING *) "
                "SELECT " + _COLUMNS + "FROM d LEFT JOIN users u ON u.id = d.uploaded_by",
                (document_id,),
            )
            return await cur.fetchone()
