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


def sqlalchemy_url(url: str) -> str:
    """Return ``url`` with the scheme SQLAlchemy needs to use the psycopg 3 driver."""
    scheme, rest = _split_url(url)
    if scheme == _SQLALCHEMY_SCHEME:
        return url
    return f"{_SQLALCHEMY_SCHEME}://{rest}"


def psycopg_url(url: str) -> str:
    """Return ``url`` with the plain scheme libpq understands (it rejects ``+psycopg``)."""
    scheme, rest = _split_url(url)
    if scheme == _PSYCOPG_SCHEME:
        return url
    return f"{_PSYCOPG_SCHEME}://{rest}"
