from datetime import datetime
from typing import Protocol
from uuid import UUID

from project_hub.shares.entities import ShareLink


class ShareRepository(Protocol):
    async def delete_expired(self, project_id: UUID, now: datetime) -> None: ...

    async def count_pending(self, project_id: UUID, now: datetime, *, except_email: str) -> int: ...

    async def put(
        self, project_id: UUID, email: str, token_hash: str, expires_at: datetime
    ) -> None: ...

    async def find_pending(self, token_hash: str, now: datetime) -> ShareLink | None: ...

    async def claim(self, share_id: UUID) -> bool: ...
