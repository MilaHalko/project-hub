"""Check that the shared contract tests passed for every database backend.

Run after ``pytest -v | tee pytest.log``:
``python -m tests.support.backend_coverage pytest.log``.
"""

import re
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Final

BACKENDS: Final = ("orm", "sql")


def _passed_pattern(backend: str) -> re.Pattern[str]:
    return re.compile(rf"_contract\.py::\S+\[{re.escape(backend)}\] PASSED")


def missing_backends(log: str, backends: Sequence[str] = BACKENDS) -> list[str]:
    """Return backends with no passing contract test in a ``pytest -v`` log."""
    return [b for b in backends if _passed_pattern(b).search(log) is None]


def main(argv: Sequence[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    path = Path(args[0])
    try:
        log = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        print(f"pytest log not found: {path}", file=sys.stderr)
        return 1

    missing = missing_backends(log)
    if missing:
        print(f"no passing contract tests for: {', '.join(missing)}", file=sys.stderr)
        return 1
    print(f"contract tests passed for: {', '.join(BACKENDS)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
