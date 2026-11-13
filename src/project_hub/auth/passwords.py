import argon2
from anyio import to_thread
from argon2.exceptions import InvalidHashError, VerificationError


class PasswordHasher:
    """Argon2id hashing that runs off the event loop (hashing is deliberately slow)."""

    def __init__(self, hasher: argon2.PasswordHasher | None = None) -> None:
        self._hasher = hasher or argon2.PasswordHasher()
        # Uses this hasher's own parameters, so tuning them keeps the dummy as slow as real hashes.
        self._dummy_hash = self._hasher.hash("dummy-password-for-timing")

    async def hash(self, password: str) -> str:
        return await to_thread.run_sync(self._hasher.hash, password)

    async def verify(self, password_hash: str, password: str) -> bool:
        """Return False on a wrong password or an unparseable hash; never raise for those."""
        try:
            return await to_thread.run_sync(self._hasher.verify, password_hash, password)
        except (VerificationError, InvalidHashError):
            return False

    async def verify_dummy(self, password: str) -> None:
        """Burn one verification so an unknown login costs as much as a wrong password."""
        await self.verify(self._dummy_hash, password)
