import logging
from logging.handlers import TimedRotatingFileHandler

log_format = '%(asctime)s | %(module)s:%(lineno)d | %(levelname)s: %(message)s'
logging.basicConfig(format=log_format)

log = logging.getLogger(__name__)

def add_file_handler(filename):
    handler = TimedRotatingFileHandler(filename=filename, when='midnight')
    handler.setFormatter(logging.Formatter(fmt=log_format))
    log.addHandler(handler)
    log.info('Writing log to %s', filename)

def set_log_level(level):
    level_upper = level.upper()
    log.setLevel(getattr(logging, level_upper))
    log.info('Log level set to %s', level_upper)

def shutdown_logging():
    logging.shutdown()
