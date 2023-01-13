import logging
import os
import sys


class Logger:
    def __init__(self):
        _logger = logging.getLogger()
        _logger.setLevel(os.getenv("LOG_LEVEL", logging.INFO))

        formatter = logging.Formatter("%(asctime)s %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(formatter)

        _logger.addHandler(handler)

        self._logger = _logger

    def logger(self):
        return self._logger


logger = Logger().logger()
