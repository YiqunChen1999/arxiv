
import os
import sys
import logging
import logging.config
from datetime import datetime
from logging import StreamHandler, FileHandler, Formatter, LoggerAdapter
from functools import lru_cache
from contextlib import contextmanager
from typing import Any, Callable
try:
    from accelerate import PartialState  # type: ignore
    ACCELERATE_AVAILABLE = True
except ImportError:
    ACCELERATE_AVAILABLE = False


PROMPT = ("[%(asctime)s] [%(levelname)s] "
          "[%(filename)s:%(lineno)s:%(funcName)s] ")
MESSAGE = "%(message)s"
DATEFMT = "%Y-%m-%d %H:%M:%S"
LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "console": {"format": PROMPT + MESSAGE, "datefmt": DATEFMT},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "console",
        },
    },
    "root": {"level": "INFO", "handlers": ["console"]},
}
logging.config.dictConfig(LOGGING_CONFIG)


class ColorFormatter(Formatter):
    BOLD = '\033[1m'
    COLOR = '\033[1;%dm'
    RESET = "\033[0m"
    GRAY, RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE = list(
        map(lambda x: '\033[1;%dm' % (30 + x), range(8))
    )

    FORMATS = {
        logging.DEBUG: BLUE + PROMPT + RESET + MESSAGE,
        logging.INFO: GREEN + PROMPT + RESET + MESSAGE,
        logging.WARNING: YELLOW + PROMPT + RESET + MESSAGE,
        logging.ERROR: RED + PROMPT + RESET + MESSAGE,
        logging.CRITICAL: BOLD + RED + PROMPT + RESET + MESSAGE,
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = Formatter(log_fmt)
        return formatter.format(record)


class Logger:
    def __init__(self, name: str | None = None) -> None:
        if name is None:
            name = __name__.split(".")[0]
        self.logger = LoggerAdapter(logging.getLogger(name), extra={})
        if ACCELERATE_AVAILABLE:
            self.state = PartialState()  # type: ignore
        else:
            self.state = None
        self.debug = self.logger.debug
        self.info = self.logger.info
        self.warning = self.logger.warning
        self.error = self.logger.error
        self.critical = self.logger.critical
        self.log = self.logger.log
        self.setLevel = self.logger.setLevel
        self.exception = self.logger.exception
        self.logger.setLevel(
            logging.INFO if self.is_rank_zero else logging.ERROR
        )
        setup_format()

    @lru_cache(None)
    def warning_once(self, *args, **kwargs):
        self.warning(*args, **kwargs)

    @property
    def rank_zero_only(self) -> Callable[..., Any]:
        if self.state is None:
            return lambda func: func
        return self.state.on_main_process

    @property
    def is_rank_zero(self) -> bool:
        if self.state is None:
            return True
        return self.state.is_main_process

    @property
    def rank(self) -> int:
        if self.state is None:
            return 0
        return self.state.process_index

    @property
    def world_size(self) -> int:
        if self.state is None:
            return 1
        return self.state.num_processes


def setup_file_handler(path: str):
    root = logging.getLogger()
    handler = FileHandler(path)
    handler.setFormatter(Formatter(PROMPT + MESSAGE))
    root.addHandler(handler)
    setup_format()


def setup_format(formatter: Formatter | None = None):
    setup_libs_format()
    root = logging.getLogger()
    for handler in root.handlers:
        if isinstance(handler, FileHandler):
            continue
        elif isinstance(handler, StreamHandler):
            if formatter is None:
                formatter = ColorFormatter(PROMPT + MESSAGE)
            handler.setFormatter(formatter)


def create_logger(name: str | None = None,
                  save_root: str | None = None,
                  file_name: str | None = None,
                  auto_setup_fmt: bool = False):
    if name is None:
        name = __name__.split(".")[0]
    logger = Logger(name)
    if save_root is not None:
        if not os.path.exists(save_root):
            os.makedirs(save_root, exist_ok=True)
        if file_name is None:
            curr_time = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
            file_name = f"{curr_time}.log"
        save_path = os.path.join(save_root, file_name)
        logger.info(f"Logger messages will be saved to {save_path}")
        setup_file_handler(save_path)
    logger.info(f"Logger {name} is created.")
    if auto_setup_fmt:
        setup_format()
    return logger


def setup_libs_format():
    try:
        from transformers.utils.logging import _get_library_root_logger  # type: ignore # noqa
    except ImportError:
        return
    logger = _get_library_root_logger()
    logger.propagate = True


@contextmanager
def disable_handlers(logger_name: str | None = None,
                     handler_types: tuple[logging.Handler] | None = None):
    logger = logging.getLogger(logger_name)
    if handler_types is None:
        handler_types = tuple()
    # Store the original states and disable specified handlers
    handler_levels: list[tuple[logging.Handler, int]] = []
    for handler in logger.handlers:
        if isinstance(handler, handler_types):  # type: ignore
            handler_levels.append((handler, handler.level))
            # Set to a level higher than CRITICAL
            handler.setLevel(logging.CRITICAL + 1)

    try:
        yield  # This is where the wrapped code will execute
    finally:
        # Restore the original states
        for handler, level in handler_levels:
            handler.setLevel(level)


@contextmanager
def disable_console_logging(logger_name: str | None = None):
    logger = logging.getLogger(logger_name)
    # Store the original states and disable console handlers
    handler_levels: list[tuple[logging.Handler, int]] = []
    for handler in logger.handlers:
        if (
                isinstance(handler, logging.StreamHandler)
                and handler.stream in (sys.stdout, sys.stderr)):
            handler_levels.append((handler, handler.level))
            # Set to a level higher than CRITICAL
            handler.setLevel(logging.CRITICAL + 1)

    try:
        yield  # This is where the wrapped code will execute
    finally:
        # Restore the original states
        for handler, level in handler_levels:
            handler.setLevel(level)
