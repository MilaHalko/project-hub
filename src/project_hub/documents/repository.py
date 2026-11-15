from typing import Protocol
from uuid import UUID

from project_hub.documents.entities import Document, NewDocument


class DocumentRepository(Protocol):
    async def add(self, document: NewDocument) -> Document: ...

    async def get(self, document_id: UUID) -> Document | None: ...
