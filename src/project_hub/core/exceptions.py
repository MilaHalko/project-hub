class DomainError(Exception):
    """Base for business-rule failures; raise directly for a generic bad request."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class NotFoundError(DomainError):
    """Raise when a requested entity does not exist."""


class PermissionDeniedError(DomainError):
    """Raise when the caller is authenticated but not allowed to do this."""


class ConflictError(DomainError):
    """Raise when the action conflicts with current state (e.g. duplicate)."""


class AuthenticationError(DomainError):
    """Raise when the caller's credentials are missing or invalid."""


class ValidationFailedError(DomainError):
    """Raise when the input is well-formed but breaks a business rule."""
