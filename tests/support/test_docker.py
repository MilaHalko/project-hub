"""Tests for the Docker test helpers (no Docker needed)."""

import sys

import pytest

from tests.support.docker import cleanup, parse_compose_ps, published_port


def test_parse_compose_ps_reads_ndjson_lines() -> None:
    out = '{"Service": "db", "State": "running"}\n\n{"Service": "api", "State": "running"}\n'
    assert parse_compose_ps(out) == [
        {"Service": "db", "State": "running"},
        {"Service": "api", "State": "running"},
    ]


def test_parse_compose_ps_reads_json_array() -> None:
    out = '[{"Service": "db", "State": "running"}, {"Service": "api", "State": "exited"}]\n'
    assert parse_compose_ps(out) == [
        {"Service": "db", "State": "running"},
        {"Service": "api", "State": "exited"},
    ]


@pytest.mark.parametrize("out", ["", "  \n\n"])
def test_parse_compose_ps_empty_output(out: str) -> None:
    assert parse_compose_ps(out) == []


def test_published_port_single_line() -> None:
    assert published_port("127.0.0.1:55000\n") == 55000


def test_published_port_uses_first_of_several_lines() -> None:
    assert published_port("0.0.0.0:55000\n[::]:55000\n") == 55000


def test_published_port_empty_raises() -> None:
    with pytest.raises(ValueError):
        published_port("")


def test_cleanup_timeout_warns_instead_of_raising() -> None:
    with pytest.warns(UserWarning, match="Cleanup timed out"):
        cleanup(sys.executable, "-c", "import time; time.sleep(5)", timeout=0.2)


def test_cleanup_ignores_non_zero_exit() -> None:
    assert cleanup(sys.executable, "-c", "raise SystemExit(3)") is None
