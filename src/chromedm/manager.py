# /usr/bin/python
# -*- coding: UTF-8 -*-
from __future__ import annotations
import asyncio
from time import time as _unix_time
from os import makedirs as _makedirs
from os.path import join as _joinpath
from os.path import abspath as _abspath
from os.path import dirname as _dirname

from chromedm import errors as _errors
from chromedm.utils import os_name as _os_name
from chromedm.utils import os_type as _os_type
from chromedm.utils import read_version_from_cmd as _read_version_from_cmd
from chromedm.utils import mac_chrome_version_cmd as _mac_chrome_version_cmd
from chromedm.utils import win_chrome_version_cmd as _win_chrome_version_cmd
from chromedm.utils import linux_chrome_version_cmd as _linux_chrome_version_cmd
from chromedm.driver import DriverDownloader as _DriverDownloader
from chromedm.driver import DriverCacheManager as _DriverCacheManager


class ChromeDM:
    """ChromeDM (ChromeDriver Manager)."""

    __instances: dict[str, ChromeDM] = {}

    def __new__(cls, dir: str = None) -> ChromeDM:
        if (_key := hash(str(dir))) not in cls.__instances:
            cls.__instances[_key] = super().__new__(cls)
            cls.__instances[_key].__init__(dir)
        return cls.__instances[_key]

    def __init__(self, dir: str = None) -> None:
        """
        :param dir: The main cache directory - `default`: `None`.
            If not provided, default to `~/chromedm/.drivers`.
            For the same cache directory, only one instance will be
            created. This avoids cross-process conflicts and reduces
            unnecessary resource usage.
        """

        # Base settings
        if not dir:
            self.__dir: str = _joinpath(_abspath(_dirname(__file__)), ".drivers")
        else:
            self.__dir: str = dir

        _makedirs(self.__dir, exist_ok=True)
        self.__os: str = _os_name()
        self.__os_type: str = _os_type(self.__os)
        self.__async_lock: asyncio.Lock = asyncio.Lock()
        self.__dcm = _DriverCacheManager(self.__dir)
        self.__version_check_time: int = 0
        # Command line
        self.__cmd: dict[str, str] = {
            "mac": _mac_chrome_version_cmd(),
            "win": _win_chrome_version_cmd(),
            "linux": _linux_chrome_version_cmd(),
        }
        # Version
        self.__chrome_version: str | None = None

    # Install
    async def install(
        self,
        latest_version_interval: int | None = None,
        *,
        proxy: str | None = None,
        timeout: int | None = None,
        max_cache: int | None = None,
    ) -> str:
        """Download & Install ChromeDriver.

        :latest_version_interval: The interval (in seconds) between checks
        for the latest driver version.
            If `None` (`default`), the package will return the cached ChromeDriver
            version (if available) that matches the major version of the local
            Chrome browser. If set to an integer greater than 0, the package will
            check for the latest driver version if last check time overdued this
            interval. Regardless of the setting, if there is no matching cached
            driver, the package will always install the latest matching driver
            version.
        :param proxy: The proxy server to use for the download.
            This should be a string representing the address of the proxy,
            e.g.:`'http://127.0.0.1:7890'`. Default `None`.
        :param timeout: Timeout for driver download.
        :param max_cache: The maximum number of cached drivers.
            If `None` (`default`), there is no limit. If set to an integer greater
            than 1, the package will remove the oldest driver from the cache when
            the number of cached drivers exceeds this limit.
        :raises: Subclass of `ChromeDMError`.
        :return: The file path of the installed executable ChromeDriver.

        ### Example:
        >>> from chromedm import ChromeDM
            cdm = ChromeDM(
                # Default cache directory: `~/chromedm/.drivers`.
                dir=None
                /or...
                # Custom cache directory: `/destop/chromedrivers`.
                dir="/destop/chromedrivers"
            )
            driver = await cdm.install(
                # Match the latest driver version after 1 day.
                latest_version_interval = 86_400,
                # Use local proxy.
                proxy="http://127.0.0.1:7890",
                # Download timeout after 10 seconds.
                timeout=10,
                # Only cache the latest 20 drivers.
                max_cache=20,
            )
        """

        async with self.__async_lock:
            try:
                return await self.__install(
                    latest_version_interval, proxy, timeout, max_cache
                )
            except _errors.ChromeDMError:
                raise
            except Exception as err:
                raise _errors.ChromeDMUnknownError(err)

    async def __install(
        self,
        latest_version_interval: int | None,
        proxy: str | None,
        timeout: int | None,
        max_cache: int | None,
    ) -> str:
        # Determine whether to check latest driver version
        if (
            isinstance(latest_version_interval, int)
            and latest_version_interval > 0
            and (_unix_time() - self.__version_check_time) > latest_version_interval
        ):
            self.__version_check_time = _unix_time()
            latest = True
        else:
            latest = False

        # Get chrome & driver version
        chrome_version = self.get_chrome_version()
        if latest:
            driver_version = await self.__get_driver_version(proxy, timeout)
        else:
            driver_version = {}

        # Match driver from cache
        driver = self.__dcm.match(
            self.__os_type,
            chrome_version,
            driver_version.get("version"),
        )
        if driver is not None:
            return driver

        # Match driver from api
        if not driver_version:
            driver_version = await self.__get_driver_version(proxy, timeout)

        if not driver_version:
            raise _errors.ApiDriverNotFoundError(
                "\nUnable to find a matching driver version "
                "for Chrome: {}".format(chrome_version)
            )

        # Download new driver
        driver = await _DriverDownloader.download_driver(
            driver_version,
            self.__os_type,
            timeout,
            proxy,
        )

        # Unpack & Cache driver
        return self.__dcm.save(
            self.__os_type,
            chrome_version,
            driver_version.get("version"),
            driver,
            max_cache,
        )

    # Version
    def get_chrome_version(self) -> str | None:
        """Get local Chrome browser version.

        :raises: Subclass of `DriverError`.
        :return: Local Chrome browser version in `str`.
        e.g.: `'114.0.5735'`.
        """

        if (version := _read_version_from_cmd(self.__cmd[self.__os])) is None:
            raise _errors.DriverVersionError(
                "Unable to verify Chrome version on local machine. "
                "Please check if Chrome has been installed properly."
            )
        self.__chrome_version = version
        return version

    async def __get_driver_version(
        self,
        proxy: str | None,
        timeout: int,
    ) -> dict[str, str]:
        """Get the latest remote ChromeDriver version
        matching local Chrome browser.

        :param proxy: The proxy server to use for the download.
            This should be a string representing the address of the proxy,
            e.g.:`'http://127.0.0.1:7890'`.
        :param timeout: Timeout for driver download.
        :raises: Subclass of `ApiError`.
        :return: Latest remote ChromeDriver version in dict.

        ### Return example:
        >>> {version: '114.0.5735.90', channel: 'googleapis'} # googleapis
        >>> {version: '115.0.5790.90', channel: 'chromelabs'} # chromelabs
        >>> {} # Not found
        """

        # Get local chrome version
        if self.__chrome_version is None:
            self.get_chrome_version()

        # Get driver version
        return await _DriverDownloader.get_driver_version(
            self.__chrome_version,
            timeout=timeout,
            proxy=proxy,
        )

    # Magic method
    def __repr__(self) -> str:
        return "<ChromeDM (dir='%s')>" % self.__dir

    def __hash__(self) -> int:
        return hash(self.__repr__())

    def __eq__(self, __o: object) -> bool:
        return hash(self) == hash(__o) if isinstance(__o, ChromeDM) else False
