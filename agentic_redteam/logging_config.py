"""Logging configuration for the agentic_redteam package.

Call configure_logging() once at application startup (e.g. scripts/serve.py).
Uses plain text by default; switch the console formatter to "json" for
structured output in production log aggregators.
"""

import logging
import logging.config

LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "format": '{"time":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","msg":"%(message)s"}'
        },
        "plain": {
            "format": "%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "plain",
            "stream": "ext://sys.stdout",
        }
    },
    "root": {
        "level": "INFO",
        "handlers": ["console"],
    },
    "loggers": {
        "agentic_redteam": {
            "level": "DEBUG",
            "propagate": True,
        }
    },
}


def configure_logging() -> None:
    """Apply LOGGING_CONFIG via dictConfig."""
    logging.config.dictConfig(LOGGING_CONFIG)
