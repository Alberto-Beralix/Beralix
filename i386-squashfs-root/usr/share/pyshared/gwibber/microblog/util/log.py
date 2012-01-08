from os.path import join, isdir, realpath
from os import makedirs
import logging
import logging.handlers

import xdg.BaseDirectory

cache_dir = realpath(join(xdg.BaseDirectory.xdg_cache_home, "gwibber"))
if not isdir(cache_dir):
  makedirs(cache_dir)

LOG_FILENAME = join(cache_dir, "gwibber.log")
loghandler = logging.handlers.RotatingFileHandler(
       LOG_FILENAME, maxBytes=20971520, backupCount=5)
logger = logging.getLogger('Gwibber')
logformatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
loghandler.setFormatter(logformatter)
logger.setLevel(logging.INFO)
logger.addHandler(loghandler)
