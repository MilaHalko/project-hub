import logging
import re
import sys
from typing import TextIO

_LOGGER_NAME = "project_hub"
_ACCESS_LOGGER_NAME = "uvicorn.access"
_TOKEN_QUERY = re.compile(r"([?&]token=)[^&\s]*")
_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


class _ProjectHubHandler(logging.StreamHandler[TextIO]):
    """Marks the handler installed by `configure_logging`, so repeat calls do not add another."""


class _HideTokenFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args
        if isinstance(args, tuple) and len(args) >= 3 and isinstance(args[2], str):
            record.args = (*args[:2], _TOKEN_QUERY.sub(r"\1***", args[2]), *args[3:])
        return True


def configure_logging() -> None:
    """Send `project_hub.*` records at INFO and above to stderr.

    uvicorn leaves the root logger at WARNING, so without this the security events logged at
    INFO would be dropped. Safe to call repeatedly; `propagate` stays on so test capture works.
    """
    logger = logging.getLogger(_LOGGER_NAME)
    logger.setLevel(logging.INFO)
    if not any(isinstance(h, _ProjectHubHandler) for h in logger.handlers):
        handler = _ProjectHubHandler(sys.stderr)
        handler.setFormatter(logging.Formatter(_FORMAT))
        logger.addHandler(handler)
    access_logger = logging.getLogger(_ACCESS_LOGGER_NAME)
    if not any(isinstance(f, _HideTokenFilter) for f in access_logger.filters):
        access_logger.addFilter(_HideTokenFilter())
