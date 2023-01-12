import logging
import os
import sys


class Logger(object):
    def __init__(self):
        logger = logging.getLogger()
        logger.setLevel(os.getenv("LOG_LEVEL", logging.INFO))

        formatter = logging.Formatter("%(asctime)s %(levelname)s - %(message)s", datefmt='%Y-%m-%d %H:%M:%S')
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(formatter)

        logger.addHandler(handler)

        self._logger = logger

    def logger(self):
        return self._logger


logger = Logger().logger()
