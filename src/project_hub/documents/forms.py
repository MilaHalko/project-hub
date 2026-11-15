from fastapi import Request
from starlette.datastructures import UploadFile
from starlette.exceptions import HTTPException

from project_hub.core.config import Settings
from project_hub.core.exceptions import ValidationFailedError
from project_hub.documents.validation import ValidFile, read_valid_file


def _checked_count(uploads: list[UploadFile], settings: Settings, *, exactly_one: bool) -> None:
    if exactly_one:
        if len(uploads) != 1:
            raise ValidationFailedError("Exactly one file is required")
        return
    if not uploads:
        raise ValidationFailedError("No files were sent")
    if len(uploads) > settings.document_max_files:
        raise ValidationFailedError(
            f"Too many files: at most {settings.document_max_files} per request"
        )


async def read_uploads(
    request: Request, settings: Settings, field: str, *, exactly_one: bool
) -> list[ValidFile]:
    try:
        async with request.form() as form:
            uploads = [item for item in form.getlist(field) if isinstance(item, UploadFile)]
            _checked_count(uploads, settings, exactly_one=exactly_one)
            return [
                await read_valid_file(upload, settings.document_max_bytes) for upload in uploads
            ]
    except HTTPException as err:
        raise ValidationFailedError(f"Invalid multipart form: {err.detail}") from err
