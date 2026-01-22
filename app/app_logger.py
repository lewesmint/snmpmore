from __future__ import annotations

import logging
import logging.handlers
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class LoggingConfig:
    level: str
    log_dir: Path
    log_file: str = "snmp-agent.log"
    console: bool = True
    max_bytes: int = 10 * 1024 * 1024
    backup_count: int = 5


class AppLogger:
    _configured: bool = False

    def __init__(self, config: LoggingConfig) -> None:
        if AppLogger._configured:
            return

        self._configure(config)
        AppLogger._configured = True

    @staticmethod
    def get(name: str | None = None) -> logging.Logger:
        return logging.getLogger(name)

    @staticmethod
    def _configure(config: LoggingConfig) -> None:
        level_name = config.level.upper()
        level = logging._nameToLevel.get(level_name, logging.INFO)

        config.log_dir.mkdir(parents=True, exist_ok=True)
        log_path = config.log_dir / config.log_file

        root = logging.getLogger()
        root.setLevel(level)

        for handler in list(root.handlers):
            root.removeHandler(handler)

        fmt = (
            "%(asctime)s.%(msecs)03d "
            "%(levelname)s "
            "%(name)s "
            "[%(threadName)s] "
            "%(message)s"
        )
        formatter = logging.Formatter(fmt=fmt, datefmt="%Y-%m-%d %H:%M:%S")

        file_handler = logging.handlers.RotatingFileHandler(
            filename=log_path,
            maxBytes=config.max_bytes,
            backupCount=config.backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)

        if config.console:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(level)
            console_handler.setFormatter(formatter)
            root.addHandler(console_handler)

        AppLogger._suppress_third_party_loggers()

    @staticmethod
    def _suppress_third_party_loggers() -> None:
        logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
        logging.getLogger("uvicorn.error").setLevel(logging.INFO)
        logging.getLogger("asyncio").setLevel(logging.WARNING)