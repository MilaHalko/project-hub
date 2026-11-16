import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Final, cast
from uuid import uuid4

DEFAULT_MAILPIT_URL: Final = "http://localhost:8025"
DEFAULT_SMTP_PORT: Final = 55436


def random_address() -> str:
    return f"{uuid4().hex}@example.com"


def _get_json(url: str, *, timeout: float) -> Any:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return json.loads(response.read())


def messages_to(
    mailpit_url: str, address: str, *, expect: int = 1, timeout: float = 5
) -> list[dict[str, Any]]:
    query = urllib.parse.quote(f'to:"{address}"')
    deadline = time.monotonic() + timeout
    while True:
        found = cast(
            dict[str, Any],
            _get_json(f"{mailpit_url}/api/v1/search?query={query}", timeout=2),
        )
        summaries = cast(list[dict[str, Any]], found["messages"])
        if len(summaries) >= expect or time.monotonic() >= deadline:
            return [
                cast(
                    dict[str, Any], _get_json(f"{mailpit_url}/api/v1/message/{s['ID']}", timeout=2)
                )
                for s in summaries
            ]
        time.sleep(0.1)


def mailpit_unreachable_reason(url: str) -> str | None:
    try:
        _get_json(f"{url}/api/v1/info", timeout=2)
    except (urllib.error.URLError, OSError, ValueError) as err:
        return str(err)
    return None
