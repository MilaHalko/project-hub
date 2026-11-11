from psycopg import ProgrammingError
from psycopg.conninfo import conninfo_to_dict

_SQLALCHEMY_SCHEME = "postgresql+psycopg"
_PSYCOPG_SCHEME = "postgresql"
_PLAIN_SCHEMES = ("postgresql", "postgres")


def _split_url(url: str) -> tuple[str, str]:
    """Split ``url`` into a supported scheme and the rest; never put the URL in an error."""
    scheme, sep, rest = url.partition("://")
    if not sep:
        raise ValueError("database URL must contain a scheme")
    if scheme != _SQLALCHEMY_SCHEME and scheme not in _PLAIN_SCHEMES:
        raise ValueError(f"unsupported database URL scheme: {scheme!r}")
    return scheme, rest


def _validated(url: str) -> tuple[str, str]:
    """Check the scheme and parse the whole URL; return ``(scheme, rest)``.

    Parser errors from libpq and SQLAlchemy quote the URL, password included, so
    a malformed URL is rejected here with a message that contains none of it.
    """
    scheme, rest = _split_url(url)
    try:
        conninfo_to_dict(f"{_PSYCOPG_SCHEME}://{rest}")
    except ProgrammingError:
        raise ValueError("invalid database URL") from None
    return scheme, rest


def sqlalchemy_url(url: str) -> str:
    """Return ``url`` with the scheme SQLAlchemy needs to use the psycopg 3 driver."""
    scheme, rest = _validated(url)
    if scheme == _SQLALCHEMY_SCHEME:
        return url
    return f"{_SQLALCHEMY_SCHEME}://{rest}"


def psycopg_url(url: str) -> str:
    """Return ``url`` with the plain scheme libpq understands (it rejects ``+psycopg``)."""
    scheme, rest = _validated(url)
    if scheme == _PSYCOPG_SCHEME:
        return url
    return f"{_PSYCOPG_SCHEME}://{rest}"
