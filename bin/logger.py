import os
from logging.handlers import QueueHandler
import logging.handlers
import queue
import sys
from bin.var_conf import config_log
from concurrent_log_handler import ConcurrentRotatingFileHandler

dict_lvl = {
    'DEBUG': logging.DEBUG,
    'INFO': logging.INFO,
    'WARNING': logging.WARNING,
    'ERROR': logging.ERROR,
    'CRITICAL': logging.CRITICAL
}

log_queue = queue.Queue()

path_to_log = config_log.path_to_save
max_bytes = config_log.max_bytes
backup_count = config_log.backup_count
format_ = config_log.format
level = config_log.level

log_dir = os.path.dirname(path_to_log)
if log_dir and not os.path.exists(log_dir):
    os.makedirs(log_dir, exist_ok=True)

file_handler = ConcurrentRotatingFileHandler(
    path_to_log,
    maxBytes=max_bytes,
    backupCount=backup_count,
    encoding='utf-8',
    use_gzip=False
)
file_handler.setFormatter(logging.Formatter(format_))
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(logging.Formatter(format_))

logger = logging.getLogger()
logger.setLevel(level)
queue_handler = logging.handlers.QueueHandler(log_queue)
logger.addHandler(queue_handler)
listener = logging.handlers.QueueListener(log_queue, file_handler, console_handler)

listener.start()



