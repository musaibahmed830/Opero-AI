"""Structured (JSON) logging.

Per docs/SECURITY_MODEL.md §8: log lines never contain passwords, OAuth
tokens, or raw email/document bodies — only resource references and
reasoning summaries. Every log record picks up the current request ID
(app/middleware/request_id.py) when one is set, so a single request's log
lines are correlatable without a tracing backend.
"""

import json
import logging
import sys

from app.core.request_context import get_request_id


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": get_request_id(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
