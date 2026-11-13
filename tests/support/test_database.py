"""Guard for the test-database helper: it must never drop a database it did not create."""

import pytest

from tests.support.database import drop_test_database


def test_drop_refuses_non_test_database() -> None:
    with pytest.raises(ValueError, match="postgres"):
        drop_test_database(
            "postgresql://u:p@127.0.0.1:1/postgres", "postgresql://u:p@127.0.0.1:1/postgres"
        )
