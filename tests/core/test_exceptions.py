import ast
from pathlib import Path

import pytest

from project_hub.core.exceptions import (
    AuthenticationError,
    ConflictError,
    DomainError,
    NotFoundError,
    PermissionDeniedError,
)


def test_domain_error_keeps_message() -> None:
    error = DomainError("boom")
    assert error.message == "boom"
    assert str(error) == "boom"


@pytest.mark.parametrize(
    "error_class",
    [NotFoundError, PermissionDeniedError, ConflictError, AuthenticationError],
)
def test_all_errors_subclass_domain_error(error_class: type[DomainError]) -> None:
    assert issubclass(error_class, DomainError)


def test_exceptions_module_does_not_import_web_framework() -> None:
    import project_hub.core.exceptions as module

    assert module.__file__ is not None
    tree = ast.parse(Path(module.__file__).read_text())
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            names.append(node.module)
    assert not [n for n in names if n.startswith(("fastapi", "starlette"))]
