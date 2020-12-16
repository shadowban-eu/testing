import gzip
import logging
from logging.handlers import TimedRotatingFileHandler
import os
import shutil

log_format = '%(asctime)s | %(module)s:%(lineno)d | %(levelname)s: %(message)s'
logging.basicConfig(format=log_format)

log = logging.getLogger(__name__)

def file_namer(name):
    return name + ".gz"

def file_rotator(source, dest):
    with open(source, "rb") as sf:
        with gzip.open(dest, "wb") as df:
            shutil.copyfileobj(sf, df)
    os.remove(source)

def add_file_handler(filename):
    handler = TimedRotatingFileHandler(filename=filename, when='midnight')
    handler.setFormatter(logging.Formatter(fmt=log_format))
    handler.namer = file_namer
    handler.rotator = file_rotator
    log.addHandler(handler)
    log.info('Writing log to %s', filename)

def set_log_level(level):
    level_upper = level.upper()
    log.setLevel(getattr(logging, level_upper))
    log.info('Log level set to %s', level_upper)

def shutdown_logging():
    logging.shutdown()
