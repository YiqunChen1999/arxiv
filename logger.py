
import os
import logging
import datetime
import os.path as osp

LOGGER_FORMAT = '{}[%(asctime)s %(levelname)s %(name)s]:{} %(message)s'


class CustomFormatter(logging.Formatter):
    BOLD = '\033[1m'
    COLOR = '\033[1;%dm'
    RESET = "\033[0m"
    GRAY, RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE = list(
        map(lambda x: '\033[1;%dm' % (30 + x), range(8))
    )

    FORMATS = {
        logging.DEBUG: LOGGER_FORMAT.format(BLUE, RESET),
        logging.INFO: LOGGER_FORMAT.format(GREEN, RESET),
        logging.WARNING: LOGGER_FORMAT.format(YELLOW, RESET),
        logging.ERROR: LOGGER_FORMAT.format(RED, RESET),
        logging.CRITICAL: LOGGER_FORMAT.format(BOLD + RED, RESET)
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)


def setup_logger(output_directory: str = None):
    kwargs = dict(
        format=LOGGER_FORMAT,
        datefmt='%m/%d/%Y %H:%M:%S',
        level=logging.INFO,
    )
    if output_directory is not None:
        log_dir = osp.join(output_directory, 'logs')
        os.makedirs(log_dir, exist_ok=True)
        curr_date = datetime.datetime.now().strftime('%Y-%m-%d')
        curr_time = datetime.datetime.now().strftime('%H-%M-%S')
        kwargs['filename'] = osp.join(log_dir, f'{curr_date}-{curr_time}.txt')
    logging.basicConfig(**kwargs)

    logger = logging.getLogger()
    handlers = (logger.handlers if len(logger.handlers)
                else logger.root.handlers)
    def is_console_handler(handler: logging.Handler):
        return (isinstance(handler, logging.StreamHandler)
                and not isinstance(handler, logging.FileHandler))

    if not any([is_console_handler(h) for h in handlers]):
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(CustomFormatter())
        logger.addHandler(console_handler)
    else:
        for handler in handlers:
            if is_console_handler(handler):
                handler.setFormatter(CustomFormatter())
