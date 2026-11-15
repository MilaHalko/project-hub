from collections.abc import Callable


# Postgres text cannot store NUL; letting one through turns into a 500 from psycopg.
def reject_nul(field: str) -> Callable[[str], str]:
    def check(value: str) -> str:
        if "\x00" in value:
            raise ValueError(f"{field} must not contain NUL characters")
        return value

    return check
