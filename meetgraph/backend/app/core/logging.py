import logging
from app.core.config import settings

def setup_logging():
    logging.basicConfig(
        level=logging.INFO if settings.APP_ENV == "development" else logging.WARNING,
        format="%(levelname)s:\t%(name)s - %(message)s"
    )
    logger = logging.getLogger("meetgraph")
    return logger

logger = setup_logging()
