# /usr/bin/python
# -*- coding: UTF-8 -*-
from logging import INFO as _INFO
from logging import getLogger as _getLogger
from logging import Formatter as _Formatter
from logging import StreamHandler as _StreamHandler

# Package logger
logger = _getLogger(__package__)
__log_format = _Formatter(
    "%(asctime)s %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
)
logger.setLevel(_INFO)
__handler = _StreamHandler()
__handler.setFormatter(__log_format)
logger.addHandler(__handler)
