"""Backend-level contract tests that need no migrated database."""

import anyio
import pytest

from tests.conftest import _build_database  # pyright: ignore[reportPrivateUsage]

pytestmark = pytest.mark.anyio

_UNREACHABLE_URL = "postgresql://project_hub:project_hub@127.0.0.1:1/x"


@pytest.mark.parametrize("backend", ["orm", "sql"])
async def test_open_fails_fast_when_database_is_unreachable(backend: str) -> None:
    db = _build_database(backend, _UNREACHABLE_URL)
    with anyio.fail_after(15), pytest.raises(Exception):  # noqa: B017
        await db.open()
    await db.close()
