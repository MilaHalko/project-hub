import pytest

from project_hub.auth.passwords import PasswordHasher

pytestmark = pytest.mark.anyio


async def test_hash_is_salted_argon2id() -> None:
    hasher = PasswordHasher()
    first = await hasher.hash("correct-horse-1")
    second = await hasher.hash("correct-horse-1")
    assert first != second
    assert first.startswith("$argon2id$")
    assert second.startswith("$argon2id$")
    assert "correct-horse-1" not in first
    assert "correct-horse-1" not in second


async def test_verify_accepts_right_and_rejects_wrong_password() -> None:
    hasher = PasswordHasher()
    password_hash = await hasher.hash("correct-horse-1")
    assert await hasher.verify(password_hash, "correct-horse-1") is True
    assert await hasher.verify(password_hash, "wrong-horse-1") is False


async def test_verify_returns_false_for_invalid_hash() -> None:
    assert await PasswordHasher().verify("not-a-hash", "x") is False
