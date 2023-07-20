# /usr/bin/python
# -*- coding: UTF-8 -*-
from aiohttp import ClientConnectorError


class ChromeDMError(Exception):
    """ChromeDM Error."""


class ChromeDMUnknownError(ChromeDMError):
    """ChromeDM Error Unknown Error."""


class DriverError(ChromeDMError):
    """Driver Error."""


class DriverVersionError(DriverError):
    """Driver Version Error."""


class DriverUnpackError(DriverError):
    """Driver Unpack Error."""


class ApiError(ChromeDMError):
    """Api Error."""


class ApiConnectionError(ApiError):
    """Api Connection Error."""


class ApiTimeoutError(ApiError, TimeoutError):
    """Api Timeout Error."""


class ApiDriverNotFoundError(ApiError):
    """Api Driver Not Found Error."""


class ApiUnknownError(ApiError):
    """Api Unknown Error."""
