from typing import Annotated

from fastapi import Depends, Request

from project_hub.storage.files import FileStorage


def get_storage(request: Request) -> FileStorage:
    storage: FileStorage | None = request.app.state.storage
    if storage is None:
        raise RuntimeError("File storage is not configured: set APP_S3_BUCKET")
    return storage


Storage = Annotated[FileStorage, Depends(get_storage)]
