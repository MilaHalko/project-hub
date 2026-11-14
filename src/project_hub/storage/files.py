import logging
from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from project_hub.core.exceptions import ServiceUnavailableError

logger = logging.getLogger(__name__)


class StorageUnavailableError(ServiceUnavailableError):
    def __init__(self) -> None:
        super().__init__("File storage is unavailable")


class FileStorage(Protocol):
    async def put(self, key: str, data: bytes, content_type: str) -> None: ...

    async def get(self, key: str) -> bytes: ...

    async def delete(self, keys: Sequence[str]) -> None: ...


async def discard_quietly(storage: FileStorage, keys: Sequence[str], *, project_id: UUID) -> None:
    try:
        await storage.delete(keys)
    except StorageUnavailableError:
        event = "document files left in storage"
        logger.warning(
            "%s project_id=%s keys=%s",
            event,
            project_id,
            list(keys),
            extra={"event": event, "project_id": project_id, "keys": list(keys)},
        )
