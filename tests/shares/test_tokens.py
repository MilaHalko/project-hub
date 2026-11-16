import re

from project_hub.shares.tokens import hash_token, new_token


def test_new_token_is_43_url_safe_characters_and_random() -> None:
    first = new_token()
    second = new_token()

    assert re.fullmatch(r"[A-Za-z0-9_-]{43}", first)
    assert re.fullmatch(r"[A-Za-z0-9_-]{43}", second)
    assert first != second


def test_hash_token_is_sha256_hex() -> None:
    assert hash_token("abc") == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
