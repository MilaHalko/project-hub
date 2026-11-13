from pathlib import Path

import pytest

from tests.support.backend_coverage import main, missing_backends

_ORM_PASSED = (
    "tests/users/test_repository_contract.py::"
    "test_add_returns_user_with_generated_fields[orm] PASSED [  8%]"
)
_SQL_PASSED = (
    "tests/users/test_repository_contract.py::"
    "test_add_returns_user_with_generated_fields[sql] PASSED [ 16%]"
)
_SQL_FAILED = (
    "tests/users/test_repository_contract.py::"
    "test_add_returns_user_with_generated_fields[sql] FAILED [ 16%]"
)
_SQL_SKIPPED = (
    "tests/users/test_repository_contract.py::"
    "test_add_returns_user_with_generated_fields[sql] SKIPPED [ 16%]"
)


def test_both_backends_passed() -> None:
    assert missing_backends(f"{_ORM_PASSED}\n{_SQL_PASSED}\n") == []


def test_missing_backend_is_reported() -> None:
    assert missing_backends(f"{_ORM_PASSED}\n") == ["sql"]


def test_failed_or_skipped_do_not_count() -> None:
    log = f"{_SQL_FAILED}\n{_SQL_SKIPPED}\n{_ORM_PASSED}\n"
    assert missing_backends(log) == ["sql"]


def test_non_contract_tests_do_not_count() -> None:
    log = (
        "tests/test_config.py::test_backend_accepts_valid_value[orm] PASSED [ 1%]\n"
        "tests/test_config.py::test_backend_accepts_valid_value[sql] PASSED [ 2%]\n"
    )
    assert missing_backends(log) == ["orm", "sql"]


def test_main_ok(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    log = tmp_path / "pytest.log"
    log.write_text(f"{_ORM_PASSED}\n{_SQL_PASSED}\n", encoding="utf-8")

    assert main([str(log)]) == 0
    assert "orm, sql" in capsys.readouterr().out


def test_main_reports_missing(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    log = tmp_path / "pytest.log"
    log.write_text(f"{_ORM_PASSED}\n", encoding="utf-8")

    assert main([str(log)]) == 1
    assert "sql" in capsys.readouterr().err


def test_main_missing_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main([str(tmp_path / "nope.log")]) == 1
    assert "not found" in capsys.readouterr().err
