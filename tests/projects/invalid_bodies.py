import pytest

INVALID_BODIES = [
    pytest.param({"name": ""}, id="empty-name"),
    pytest.param({"name": "   "}, id="blank-name"),
    pytest.param({"name": "x" * 101}, id="name-101"),
    pytest.param({"name": "Dip\x00loma"}, id="name-nul"),
    pytest.param({"name": "Dip\nloma"}, id="name-newline"),
    pytest.param({"name": "Dip\tloma"}, id="name-tab"),
    pytest.param({"name": "Dip\x7floma"}, id="name-del"),
    pytest.param({"name": "ok", "description": "x" * 2001}, id="description-2001"),
    pytest.param({"name": "ok", "description": "a\x00b"}, id="description-nul"),
    pytest.param({}, id="name-missing"),
]
