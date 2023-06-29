# /usr/bin/python
# -*- coding: UTF-8 -*-
from os import chmod as _chmod
from os import getcwd as _getcwd
from os import getenv as _getenv
from sys import platform as _sys_platform
from zipfile import ZipInfo as _ZipInfo, ZipFile
from platform import machine as _platform_machine
from subprocess import Popen as _subprocess_Popen
from subprocess import PIPE as _PIPE, DEVNULL as _DEVNULL

from chromedm import errors as _errors
from chromedm.settings import VERSION_CAMMAND_RE as _VERSION_CAMMAND_RE
from chromedm.settings import VERSION_COMMAND_MAPPER as _VERSION_COMMAND_MAPPER

_OS_MAP: dict[str, str] = {
    "darwin": "mac",
    "linux": "linux",
    "linux2": "linux",
    "win32": "win",
    "cygwin": "win",
    "msys": "win",
    "os2": "os2",
    "os2emx": "os2",
    "riscos": "riscos",
    "atheos": "atheos",
    "freebsd": "freebsd",
    "freebsd6": "freebsd",
    "freebsd7": "freebsd",
    "freebsd8": "freebsd",
    "freebsdN": "freebsd",
}


def os_name() -> str:
    """Get the name of the operating system.
    All possible values: `"mac"`, `"linux"`, `"win"`,
    `"os2"`, `"riscos"`, `"atheos"`, `"freebsd"`, `"unknown"`
    """

    return _OS_MAP.get(_sys_platform, "unknown")


def os_bit() -> int:
    """Get the bit of the operating system.
    All possible values: `32`, `64`
    """

    return 64 if _platform_machine().endswith("64") else 32


def os_is_arm() -> bool:
    """Check if the operating system based on arm."""

    return bool(_platform_machine())


def os_type(os: str) -> str:
    """Get the type of the operating system."""

    if os == "mac":
        return ("mac_arm" if os_is_arm() else "mac") + str(os_bit())
    elif os == "win":
        return "win" + str(os_bit())
    elif os == "linux":
        return "linux" + str(os_bit())
    else:
        raise _errors.ChromeDMError(
            "<ChromeMD> Don't support current operating system: '{}'".format(os)
        )


def mac_chrome_version_cmd() -> str:
    """The command line to check local Chrome version
    on MacOS.

    :return: e.g.:
    "/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome -- version"
    """

    return " || ".join(["%s --version" % i for i in _VERSION_COMMAND_MAPPER["mac"]])


def linux_chrome_version_cmd() -> str:
    """The command line to check local Chrome version 
    on Linux.

    :return: e.g.: 
    "google-chrome --version || google-chrome-stable --version || \
    google-chrome-beta --version || google-chrome-dev --version"
    """

    ignore_error = " 2>/dev/null" if _getenv("WDM_LOG_LEVEL") == "0" else ""
    return " || ".join(
        ["%s --version%s" % (i, ignore_error) for i in _VERSION_COMMAND_MAPPER["linux"]]
    )


def win_chrome_version_cmd() -> str:
    """The command line to check local Chrome version
    on Windows.
    """

    def determine_powershell() -> str:
        """Returns "True" if runs in Powershell and "False"
        if another console.
        """

        cmd = "(dir 2>&1 *`|echo CMD);&<# rem #>echo powershell"
        with _subprocess_Popen(
            cmd,
            stdout=_PIPE,
            stderr=_DEVNULL,
            stdin=_DEVNULL,
            shell=True,
        ) as stream:
            stdout = stream.communicate()[0].decode()
        return "" if stdout == "powershell" else "powershell"

    first_hit = """$tmp = {expression}; if ($tmp) {{echo $tmp; Exit;}};"""
    script = "$ErrorActionPreference='silentlycontinue'; " + " ".join(
        [first_hit.format(expression=i) for i in _VERSION_COMMAND_MAPPER["win"]]
    )
    return '%s -NoProfile "%s"' % (determine_powershell(), script)


def read_version_from_cmd(cmd) -> str | None:
    """Read version from command line."""

    with _subprocess_Popen(
        cmd,
        stdout=_PIPE,
        stderr=_DEVNULL,
        stdin=_DEVNULL,
        shell=True,
    ) as stream:
        stdout = stream.communicate()[0].decode()
        version = _VERSION_CAMMAND_RE.search(stdout)
    return version.group(0) if version else None


class LinuxZipFileWithPermissions(ZipFile):
    """Extract files in linux with correct permissions."""

    def extract(self, member, path=None, pwd=None):
        if not isinstance(member, _ZipInfo):
            member = self.getinfo(member)

        if path is None:
            path = _getcwd()

        ret_val = self._extract_member(member, path, pwd)  # noqa
        attr = member.external_attr >> 16
        _chmod(ret_val, attr)
        return ret_val
