from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from project_hub.documents.entities import Document, NewDocument, ReplacedFile


class DocumentRepository(Protocol):
    async def add(self, document: NewDocument) -> Document: ...

    async def get(self, document_id: UUID) -> Document | None: ...

    async def replace_file(self, document_id: UUID, file: ReplacedFile) -> Document | None: ...

    async def list_for_project(self, project_id: UUID) -> list[Document]: ...

    async def list_for_projects(
        self, project_ids: Sequence[UUID]
    ) -> dict[UUID, list[Document]]: ...

    async def delete(self, document_id: UUID) -> Document | None: ...
