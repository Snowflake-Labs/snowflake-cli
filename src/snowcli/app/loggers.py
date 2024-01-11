import copy
import logging
import logging.config
from pathlib import Path
from typing import Any

import typer
from snowcli.api.config import (
    get_logs_config,
    is_default_logs_path,
)
from snowcli.api.exceptions import InvalidLogsConfiguration

_DEFAULT_LOG_FILENAME = "snowcli.log"

DEFAULT_LOGGING_CONFIG: dict[str, Any] = {
    "version": 1,
    "disable_existing_loggers": True,
    "formatters": {
        "default_formatter": {
            "class": "logging.Formatter",
            "format": "%(asctime)s %(levelname)s %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
        "detailed_formatter": {
            "class": "logging.Formatter",
            "format": "%(asctime)s %(levelname)s [%(name)s] %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    "filters": {},
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "default_formatter",
            "level": logging.ERROR,
        },
        "file": {
            "class": "logging.handlers.TimedRotatingFileHandler",
            "filename": None,
            "when": "midnight",
            "formatter": "detailed_formatter",
            "level": logging.INFO,
        },
    },
    "loggers": {
        "snowcli": {
            "level": logging.NOTSET,
            "handlers": ["console", "file"],
        },
        "snowflake": {
            "level": logging.NOTSET,
        },
    },
}


class FileLogsConfig:
    def __init__(self, debug: bool) -> None:
        config = get_logs_config()

        self.path: Path = Path(config["path"])
        self.save_logs: bool = config["save_logs"]
        self.level: int = logging.getLevelName(config["level"].upper())
        if debug:
            self.level = logging.DEBUG

        self._check_log_level(config)
        if self.save_logs:
            self._check_logs_directory_exists()

    def _check_logs_directory_exists(self):
        if not self.path.exists():
            if is_default_logs_path(self.path):
                self.path.mkdir(parents=True)
            else:
                raise InvalidLogsConfiguration(
                    f"Directory '{self.path}' does not exist"
                )

    def _check_log_level(self, config):
        possible_log_levels = [
            logging.DEBUG,
            logging.INFO,
            logging.WARN,
            logging.ERROR,
            logging.CRITICAL,
        ]
        if self.level not in possible_log_levels:
            raise InvalidLogsConfiguration(
                f"Invalid 'level' value set in [logs] section: {config['level']}. "
                f"'level' should be one of: {' / '.join(logging.getLevelName(lvl) for lvl in possible_log_levels)}"
            )

    @property
    def filename(self):
        return self.path / _DEFAULT_LOG_FILENAME


def create_loggers(verbose: bool, debug: bool):
    """Creates a logger depending on the SnowCLI parameters and config file.
    verbose == True - print info and higher logs in default format
    debug == True - print debug and higher logs in debug format
    none of above - print only error logs in default format
    """
    config = copy.deepcopy(DEFAULT_LOGGING_CONFIG)

    if verbose and debug:
        raise typer.BadParameter("Only one parameter `verbose` or `debug` is possible")
    elif debug:
        config["handlers"]["console"].update(
            level=logging.DEBUG,
            formatter="detailed_formatter",
        )
    elif verbose:
        config["handlers"]["console"].update(level=logging.INFO)

    global_log_level = config["handlers"]["console"]["level"]

    file_logs_config = FileLogsConfig(debug=debug)
    if file_logs_config.save_logs:
        config["handlers"]["file"].update(
            level=file_logs_config.level,
            filename=file_logs_config.filename,
        )
        if file_logs_config.level < global_log_level:
            global_log_level = file_logs_config.level
    else:
        del config["handlers"]["file"]
        config["loggers"]["snowcli"]["handlers"].remove("file")

    config["loggers"]["snowcli"]["level"] = global_log_level
    config["loggers"]["snowflake"]["level"] = global_log_level

    logging.config.dictConfig(config)
