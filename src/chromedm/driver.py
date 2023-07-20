# /usr/bin/python
# -*- coding: UTF-8 -*-
from __future__ import annotations
import asyncio
from shutil import rmtree as _rmtree
from os import makedirs as _makedirs
from os.path import join as _joinpath
from os.path import exists as _exists, sep as _sep
from packaging.version import parse as _parse_version
from datetime import datetime as _datetime
from tarfile import open as _tarfile_open
from tarfile import ReadError as _ReadError
from subprocess import call as _subprocess_call

from pandas import DataFrame as _DataFrame
from pandas import read_parquet as _read_parquet
from aiohttp import ClientSession as _ClientSession
from aiohttp import ClientResponse as _ClientResponse

from chromedm import errors as _errors
from chromedm.logs import logger as _logger
from chromedm.utils import os_name as _os_name
from chromedm.utils import ZipFile as _ZipFile
from chromedm.utils import LinuxZipFileWithPermissions as _LinuxZipFileWithPermissions
from chromedm.settings import DRIVER_HOST_URL as _DRIVER_HOST_URL
from chromedm.settings import MAC_SP_VERION_M1 as _MAC_SP_VERION_M1
from chromedm.settings import LATEST_RELEASE_URL as _LATEST_RELEASE_URL
from chromedm.settings import DRIVER_FILENAME_RE as _DRIVER_FILENAME_RE

__all__ = ["Driver", "DriverDownloader", "DriverCacheManager"]


class Driver:
    """The downloaded webdriver."""

    def __init__(self, content: bytes, response: _ClientResponse):
        """
        :param content: The webdriver content in bytes.
        :param response: The driver download http response.
        """

        self.__content: bytes = content
        self.__response: _ClientResponse = response
        self.__name: str = "chromedriver"

    @property
    def filename(self) -> str:
        """The downloaded webdriver filename."""

        try:
            filename = _DRIVER_FILENAME_RE.findall(
                self.__response.headers["content-disposition"]
            )[0]
        except KeyError:
            filename = f"{self.__name}.zip"
        except IndexError:
            filename = f"{self.__name}.exe"

        if '"' in filename:
            filename = filename.replace('"', "")

        return filename

    # Unpack
    def unpack(self, dir: str) -> str:
        """Unpack the downloaded webdriver.

        :param dir: The directory to unpack the webdriver.
        :return: The file path of the executable binary.
        """

        def extract(content_path: str) -> str:
            # Unpack driver files
            if content_path.endswith(".zip"):
                files = self.__extract_zip(content_path, dir)
            elif content_path.endswith(".tar.gz"):
                files = self.__extract_tar_file(content_path, dir)

            # Return unpacked binary filename
            if len(files) == 1:
                return files[0]

            for file in files:
                if "/" in file:
                    if file.split("/")[-1].startswith(self.__name):
                        return file
                elif self.__name in file:
                    return file

            raise _errors.DriverUnpackError(
                "Can't find binary for {} among: {}".format(
                    self.__name, ", ".join(map(repr, files))
                )
            )

        # Create directory
        _makedirs(dir, exist_ok=True)

        # Save driver content
        content_path = _joinpath(dir, self.filename)
        with open(content_path, "wb") as f:
            f.write(self.__content)

        # Extra driver binary
        binary_path = _joinpath(dir, extract(content_path))

        # Grant permission
        self.__grant_permission(binary_path)

        # Return binary path
        return binary_path

    def __extract_zip(self, path: str, dir: str) -> list[str]:
        """Extracts the downloaded webdriver `zip` file."""

        zip_class = _LinuxZipFileWithPermissions if _os_name == "linux" else _ZipFile
        archive = zip_class(path)
        try:
            archive.extractall(dir)
        except Exception as err:
            if err.args[0] not in [26, 13] and err.args[1] not in [
                "Text file busy",
                "Permission denied",
            ]:
                raise err
        return archive.namelist()

    def __extract_tar_file(self, path: str, dir: str) -> list[str]:
        """Extracts the downloaded webdriver `tar` file."""

        try:
            tar = _tarfile_open(path, mode="r:gz")
        except _ReadError:
            tar = _tarfile_open(path, mode="r:bz2")
        members = tar.getmembers()
        tar.extractall(dir)
        tar.close()
        return [x.name for x in members]

    def __grant_permission(self, path: str):
        """Gives executable permission to the unpacked
        driver binary.
        """

        _subprocess_call(["chmod", "u+x", path])


class DriverDownloader:
    """The webdriver downloader."""

    @staticmethod
    async def get_driver_version(
        chrome_version: str,
        timeout: int | None = None,
        proxy: str | None = None,
    ) -> str:
        """Get the latest ChromeDriver version based on Chrome version.

        :param version: The Chrome browser version.
        :param timeout: The request timeout in seconds.
        :param proxy: The proxy server to use for the download.
            This should be a string representing the address of the proxy,
            e.g.:`'http://127.0.0.1:7890'`. Default `None`.
        :return: The webdriver version.
        """
        # Construct request url
        url = "%s_%s" % (_LATEST_RELEASE_URL, chrome_version)

        # Request driver version
        async with _ClientSession() as session:
            while True:
                try:
                    async with session.get(url, timeout=timeout, proxy=proxy) as res:
                        # Success
                        if (code := res.status) == 200:
                            return (await res.text()).strip()
                        # Rate Limit Error
                        elif code == 401:
                            _logger.warning("Exceeded api rate limit, please wait...")
                            await asyncio.sleep(1)
                        # Driver Not Found
                        elif code == 404:
                            raise _errors.ApiDriverNotFoundError(
                                "\nDriver not found from api: {}".format(res.url)
                            )
                        # Unknown Error
                        else:
                            raise _errors.ApiUnknownError(
                                "\nUnknown error from api: {}"
                                "\nResponse body: {}"
                                "\nResponse headers: {}".format(
                                    res.url, await res.text(), dict(res.headers)
                                )
                            )
                # Connection error
                except _errors.ClientConnectorError as err:
                    raise _errors.ApiConnectionError(
                        "Can't not connect to api: {}".format(url)
                    ) from err
                # Timeout Error
                except asyncio.TimeoutError as err:
                    raise _errors.ApiTimeoutError(
                        "Timeout when retrieving driver download src "
                        "from api: {}".format(url)
                    ) from err

    @staticmethod
    async def download_driver(
        driver_version: str,
        os_type: str,
        timeout: int | None = None,
        proxy: str | None = None,
    ) -> Driver:
        """Download the ChromeDriver.

        :param driver_version: The ChromeDriver version.
        :param os_type: The operating system type.
        :param timeout: The request timeout in seconds.
        :param proxy: The proxy server to use for the download.
            This should be a string representing the address of the proxy,
            e.g.:`'http://127.0.0.1:7890'`. Default `None`.
        :return: The downloaded ChromeDrive <`class Driver'>.
        """

        # Adjust os type for MacOS M1 (Legacy version)
        if (
            os_type.startswith("mac")
            and _parse_version(driver_version) < _MAC_SP_VERION_M1
        ):
            os_type = os_type.replace("mac_arm64", "mac64_m1")

        # Construct download url
        url = "%s/%s/chromedriver_%s.zip" % (
            _DRIVER_HOST_URL,
            driver_version,
            os_type,
        )

        # Download driver
        async with _ClientSession() as session:
            while True:
                try:
                    async with session.get(
                        url,
                        chunked=True,
                        timeout=timeout,
                        proxy=proxy,
                    ) as res:
                        # Success
                        if (code := res.status) == 200:
                            return Driver(await res.content.read(), res)
                        # Rate Limit Error
                        elif code == 401:
                            _logger.warning("Exceeded api rate limit, please wait...")
                            await asyncio.sleep(1)
                        # Driver Not Found
                        elif code == 404:
                            raise _errors.ApiDriverNotFoundError(
                                "\nThere is not such driver from: {}"
                                "\nResponse body: {}"
                                "\nResponse headers: {}".format(
                                    res.url, await res.text(), dict(res.headers)
                                )
                            )
                        # Unknown Error
                        else:
                            raise _errors.ApiUnknownError(
                                "\nUnknown error from api: {}"
                                "\nResponse body: {}"
                                "\nResponse headers: {}".format(
                                    res.url, await res.text(), dict(res.headers)
                                )
                            )
                # Connection error
                except _errors.ClientConnectorError as err:
                    raise _errors.ApiConnectionError(
                        "Can't not connect to api: {}".format(url)
                    ) from err
                except asyncio.TimeoutError as err:
                    raise _errors.ApiTimeoutError(
                        "Timeout when downloading driver from api: {}".format(url)
                    ) from err


class DriverCacheManager:
    """Driver cache manager."""

    __SORT_ORDER: list[str] = [
        "time",
        "os_type",
        "chrome_version",
        "driver_version",
        "driver_folder",
    ]
    __METADATA_FILENAME: str = "metadata.parquet"
    __instances: dict[str, DriverCacheManager] = {}

    def __new__(cls, dir: str) -> DriverCacheManager:
        if (_key := hash(dir)) not in cls.__instances:
            cls.__instances[_key] = super().__new__(cls)
            cls.__instances[_key].__init__(dir)
        return cls.__instances[_key]

    def __init__(self, dir: str) -> None:
        """:param dir: The main cache directory."""

        self.__dir: str = dir
        self.__metadata: _DataFrame = None
        self.__metadata_path = _joinpath(self.__dir, self.__METADATA_FILENAME)

    def match(
        self,
        os_type: str,
        chrome_version: str,
        driver_version: str | None,
    ) -> str | None:
        """Load the matching binary driver path from cache.

        :param os_type: System os type.
        :param chrome_version: Chrome browser version.
        :param driver_version: ChromeDriver version.
        :return: binary driver path if matched, else None.
        """

        # Load metadata
        metadata = self.__load_metadata()

        # Match binary driver
        if driver_version is None:
            # . Loose match
            query = 'os_type == "%s" and chrome_version == "%s"' % (
                os_type,
                chrome_version,
            )
        else:
            # . Strict match
            query = (
                'os_type == "%s" and chrome_version == "%s" and driver_version == "%s"'
                % (os_type, chrome_version, driver_version)
            )
        match_idx = metadata.query(query).sort_values(["time"], ascending=False).index

        # Return binary driver path
        for idx in match_idx:
            if _exists(path := metadata.loc[idx, "driver_path"]):
                return path
        return None

    def save(
        self,
        os_type: str,
        chrome_version: str,
        driver_version: str,
        driver: Driver,
        max_cache: int | None,
    ) -> str:
        """Save driver to cache.

        :param os_type: System os type.
        :param chrome_version: Chrome Brwoser version.
        :param driver_version: ChromeDriver version.
        :param max_cache: The maximum number of cached drivers.
            If `None`, there is no limit. If set to an integer greater than 1,
            the package will remove the oldest driver from the cache when the
            number of cached drivers exceeds this limit.
        :return: The binary driver path.
        """

        # Remove expired cache
        self.__remove_expiry(max_cache)

        # Create driver directory
        dir = _joinpath(
            self.__dir,
            "%s_%s" % (os_type.replace(".", "_"), chrome_version.replace(".", "_")),
            driver_version.replace(".", "_"),
        )

        # Unpack driver
        driver_path = driver.unpack(dir)

        # Load metadata
        metadata = self.__load_metadata()

        # Query matching driver
        query = (
            'os_type == "%s" and chrome_version == "%s" and driver_version == "%s"'
            % (os_type, chrome_version, driver_version)
        )
        match_idx = metadata.query(query).index

        # Update metadata
        if not match_idx.empty:
            metadata.loc[match_idx] = [
                _datetime.now().replace(microsecond=0),
                os_type,
                chrome_version,
                driver_version,
                driver_path,
                dir,
            ]

        # Insert metadata
        else:
            metadata.loc[len(metadata)] = [
                _datetime.now().replace(microsecond=0),
                os_type,
                chrome_version,
                driver_version,
                driver_path,
                dir,
            ]

        # Save metadata
        self.__save_metadata(metadata)

        # Return binary driver path
        return driver_path

    def __load_metadata(self) -> _DataFrame:
        """Load metadata."""

        # . Create empty metadata.
        def create_metadata() -> _DataFrame:
            metadata = _DataFrame(
                columns=[
                    "time",
                    "os_type",
                    "chrome_version",
                    "driver_version",
                    "driver_path",
                    "driver_folder",
                ]
            )
            _makedirs(self.__dir, exist_ok=True)
            metadata.to_parquet(self.__metadata_path)
            return metadata

        # Load from memory
        if self.__metadata is not None:
            return self.__metadata.copy()

        # Create empty metadata
        elif not _exists(self.__metadata_path):
            self.__metadata = create_metadata()

        # Load local metadata
        else:
            self.__metadata = _read_parquet(self.__metadata_path)

        # Return metadata
        return self.__metadata.copy()

    def __save_metadata(self, metadata: _DataFrame) -> None:
        """Save metadata."""

        # Save to memory
        self.__metadata = metadata.drop_duplicates().sort_values(
            self.__SORT_ORDER, ignore_index=True
        )

        # Save to local
        self.__metadata.to_parquet(self.__metadata_path)

    def __remove_expiry(self, max_cache: int) -> None:
        """Remove expired cache."""

        # Check for expired cache
        if max_cache is None:
            return None
        elif not isinstance(max_cache, int) or max_cache < 1:
            _logger.warning(
                "Parameter 'max_cache' must be an `int` greater than or equal "
                "to 1. If you want to disable cache removal, set it to None."
            )
            return None
        elif len(metadata := self.__load_metadata()) <= (_max := max_cache - 1):
            return None

        # Find expired cache
        metadata = metadata.sort_values(["time"], ignore_index=True)
        expired = metadata[~metadata.index.isin(metadata.tail(_max).index)].copy()

        # Remove local files
        for _, row in expired.iterrows():
            driver_folder: str = row["driver_folder"]
            try:
                _rmtree(driver_folder[: driver_folder.rfind(_sep)])
            except Exception as err:
                _logger.warning(
                    "Failed to remove expired local cache: {}"
                    "\n{}".format(driver_folder, err)
                )

        # Drop from metadata
        metadata = metadata.drop(expired.index, axis=0)

        # Save metadata
        self.__save_metadata(metadata)

    # Magic methods
    def __repr__(self) -> str:
        return "<DriverCacheManager (dir='%s')>" % self.__dir

    def __hash__(self) -> int:
        return hash(self.__repr__())

    def __eq__(self, __o: object) -> bool:
        return hash(self) == hash(__o) if isinstance(__o, DriverCacheManager) else False
