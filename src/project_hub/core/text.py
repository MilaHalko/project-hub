# Postgres text cannot store NUL; letting one through turns into a 500 from psycopg.
def reject_nul(value: str) -> str:
    if "\x00" in value:
        raise ValueError("Value must not contain NUL characters")
    return value
