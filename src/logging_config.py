import json
import logging
from datetime import datetime, timezone

from src.config import settings

from src.request_context import request_id_context

class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        request_id = request_id_context.get()

        if request_id:
            log_record["request_id"] = request_id

        optional_fields = (
            "request_method",
            "request_path",
            "status_code",
            "duration_ms",
            "repository",
            "external_status_code",
            "rate_limit_remaining",
            "rate_limit_reset",
            "retry_after",
        )

        for field in optional_fields:
            if hasattr(record, field):
                log_record[field] = getattr(record, field)

        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_record)


def configure_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(settings.log_level.upper())