import argparse
import json
import sys
import uuid
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

FILES = Path(__file__).parent / "files"

USERS = {
    "anna": "anna1234",
    "boris": "boris1234",
    "vera": "vera12345",
}

PROJECTS = [
    {
        "owner": "anna",
        "name": "Дипломный проект",
        "description": "План диплома, требования и заметки со встреч с ментором.",
        "members": ["boris"],
        "documents": ["thesis-plan.pdf", "requirements.docx"],
    },
    {
        "owner": "anna",
        "name": "Сайт кофейни",
        "description": "Лендинг и меню для кофейни у дома.",
        "members": [],
        "documents": [],
    },
    {
        "owner": "boris",
        "name": "Поездка в Карпаты",
        "description": "Маршрут, бюджет и список вещей.",
        "members": ["anna"],
        "documents": ["budget.docx"],
    },
]

CONTENT_TYPES = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


class Api:
    def __init__(self, base: str) -> None:
        self.base = base.rstrip("/")

    def call(
        self,
        method: str,
        path: str,
        *,
        token: str | None = None,
        body: dict | None = None,
        data: bytes | None = None,
        content_type: str | None = None,
    ) -> tuple[int, object]:
        headers = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        if body is not None:
            data = json.dumps(body).encode()
            content_type = "application/json"
        if content_type:
            headers["Content-Type"] = content_type
        request = Request(self.base + path, data=data, headers=headers, method=method)
        try:
            with urlopen(request, timeout=15) as response:
                raw = response.read()
                return response.status, json.loads(raw) if raw else None
        except HTTPError as err:
            raw = err.read()
            try:
                return err.code, json.loads(raw)
            except ValueError:
                return err.code, raw.decode(errors="replace")

    def expect(self, ok: set[int], method: str, path: str, **kwargs: object) -> object:
        status, payload = self.call(method, path, **kwargs)
        if status not in ok:
            sys.exit(f"{method} {path} -> {status}: {payload}")
        return payload


def sign_in(api: Api, login: str, password: str) -> str:
    status, payload = api.call(
        "POST", "/auth", body={"login": login, "password": password, "repeat_password": password}
    )
    if status == 201:
        print(f"registered {login}")
    elif status != 409:
        sys.exit(f"POST /auth {login} -> {status}: {payload}")
    token = api.expect({200}, "POST", "/login", body={"login": login, "password": password})
    return token["access_token"]


def multipart(field: str, path: Path) -> tuple[bytes, str]:
    boundary = uuid.uuid4().hex
    head = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="{field}"; filename="{path.name}"\r\n'
        f"Content-Type: {CONTENT_TYPES[path.suffix]}\r\n\r\n"
    ).encode()
    tail = f"\r\n--{boundary}--\r\n".encode()
    return head + path.read_bytes() + tail, f"multipart/form-data; boundary={boundary}"


def seed(api: Api, with_documents: bool) -> None:
    tokens = {login: sign_in(api, login, password) for login, password in USERS.items()}
    for spec in PROJECTS:
        token = tokens[spec["owner"]]
        mine = api.expect({200}, "GET", "/projects?role=owner&limit=100", token=token)
        project = next((p for p in mine if p["name"] == spec["name"]), None)
        if project is None:
            project = api.expect(
                {201},
                "POST",
                "/projects",
                token=token,
                body={"name": spec["name"], "description": spec["description"]},
            )
            print(f"created project {spec['name']!r} for {spec['owner']}")
        pid = project["id"]
        members = api.expect({200}, "GET", f"/project/{pid}/members", token=token)
        present = {m["login"] for m in members}
        for login in spec["members"]:
            if login not in present:
                api.expect({201}, "POST", f"/project/{pid}/invite?user={login}", token=token)
                print(f"  invited {login}")
        if not with_documents:
            continue
        documents = api.expect({200}, "GET", f"/project/{pid}/documents", token=token)
        names = {d["name"] for d in documents}
        for file_name in spec["documents"]:
            if file_name not in names:
                data, content_type = multipart("files", FILES / file_name)
                api.expect(
                    {201},
                    "POST",
                    f"/project/{pid}/documents",
                    token=token,
                    data=data,
                    content_type=content_type,
                )
                print(f"  uploaded {file_name}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Fill a running Project Hub with demo data.")
    parser.add_argument("--api", default="http://127.0.0.1:8020")
    parser.add_argument("--documents", action="store_true", help="also upload demo documents")
    args = parser.parse_args()
    api = Api(args.api)
    api.expect({200}, "GET", "/health")
    seed(api, args.documents)
    print("done")


if __name__ == "__main__":
    main()
