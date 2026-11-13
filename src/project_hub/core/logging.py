import logging
import sys

_LOGGER_NAME = "project_hub"
_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def configure_logging() -> None:
    """Send `project_hub.*` records at INFO and above to stderr.

    uvicorn leaves the root logger at WARNING, so without this the security events logged at
    INFO would be dropped. Safe to call repeatedly; `propagate` stays on so test capture works.
    """
    logger = logging.getLogger(_LOGGER_NAME)
    logger.setLevel(logging.INFO)
    if not any(getattr(h, "_project_hub", False) for h in logger.handlers):
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter(_FORMAT))
        handler._project_hub = True  # pyright: ignore[reportAttributeAccessIssue]
        logger.addHandler(handler)
