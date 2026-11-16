import json
import subprocess
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit, urlunsplit

from tests.support.docker import ROOT

IMAGE = "public.ecr.aws/lambda/python:3.13"
COMMAND_TIMEOUT = 900
HOST_FROM_CONTAINER = "host.docker.internal"


def tail(text: str, limit: int = 4000) -> str:
    return text[-limit:]


def run(*args: str) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        args, check=False, capture_output=True, text=True, cwd=ROOT, timeout=COMMAND_TIMEOUT
    )
    assert result.returncode == 0, (
        f"{' '.join(args)} exited with {result.returncode}\n"
        f"--- stdout ---\n{tail(result.stdout)}\n--- stderr ---\n{tail(result.stderr)}"
    )
    return result


def for_container(url: str) -> str:
    parts = urlsplit(url)
    userinfo = parts.netloc.rpartition("@")[0]
    port = f":{parts.port}" if parts.port else ""
    netloc = f"{userinfo}@" if userinfo else ""
    return urlunsplit(parts._replace(netloc=f"{netloc}{HOST_FROM_CONTAINER}{port}"))


def invoke(port: int, event: dict[str, object], timeout: float = 30) -> tuple[int, str]:
    url = f"http://127.0.0.1:{port}/2015-03-31/functions/function/invocations"
    request = urllib.request.Request(url, data=json.dumps(event).encode(), method="POST")
    deadline = time.monotonic() + timeout
    while True:
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.status, response.read().decode()
        except urllib.error.HTTPError as error:
            return error.code, error.read().decode()
        except (urllib.error.URLError, OSError):
            if time.monotonic() >= deadline:
                raise
            time.sleep(0.5)
