import logging
import sys
from typing import TextIO

_LOGGER_NAME = "project_hub"
_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


class _ProjectHubHandler(logging.StreamHandler[TextIO]):
    pass


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
