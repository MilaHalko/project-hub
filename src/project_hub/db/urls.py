_SQLALCHEMY_SCHEME = "postgresql+psycopg"
_PLAIN_SCHEMES = ("postgresql", "postgres")


def sqlalchemy_url(url: str) -> str:
    """Return ``url`` with the scheme SQLAlchemy needs to use the psycopg 3 driver."""
    scheme, sep, rest = url.partition("://")
    if not sep:
        raise ValueError("database URL must contain a scheme")
    if scheme == _SQLALCHEMY_SCHEME:
        return url
    if scheme in _PLAIN_SCHEMES:
        return f"{_SQLALCHEMY_SCHEME}://{rest}"
    raise ValueError(f"unsupported database URL scheme: {scheme!r}")
