"""Small structured JSON logging setup without a third-party logging dependency."""

import json
import logging
from datetime import datetime, timezone

from app.core.request_context import request_id_context


class JsonFormatter(logging.Formatter):
    """Format log records as one JSON object per line."""

    def format(self, record: logging.LogRecord) -> str:
        event: dict[str, object] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        request_id = request_id_context.get()
        if request_id:
            event["request_id"] = request_id
        if record.exc_info:
            event["exception_type"] = record.exc_info[0].__name__ if record.exc_info[0] else None
        return json.dumps(event, ensure_ascii=False, default=str)


def configure_logging(level: str) -> None:
    """Configure root logging using a JSON formatter."""
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(level.upper())
