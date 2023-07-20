#!/usr/bin/env python
# -*- coding: UTF-8 -*-
from re import compile as _compile
from packaging.version import parse as _parse_version

DRIVER_HOST_URL: str = "https://chromedriver.storage.googleapis.com"
LATEST_RELEASE_URL: str = DRIVER_HOST_URL + "/LATEST_RELEASE"
VERSION_COMMAND_MAPPER: dict[str, list[str]] = {
    "linux": [
        "google-chrome",
        "google-chrome-stable",
        "google-chrome-beta",
        "google-chrome-dev",
    ],
    "mac": [r"/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome"],
    "win": [
        r'(Get-Item -Path "$env:PROGRAMFILES\Google\Chrome\Application\chrome.exe").VersionInfo.FileVersion',
        r'(Get-Item -Path "$env:PROGRAMFILES (x86)\Google\Chrome\Application\chrome.exe").VersionInfo.FileVersion',
        r'(Get-Item -Path "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe").VersionInfo.FileVersion',
        r'(Get-ItemProperty -Path Registry::"HKCU\SOFTWARE\Google\Chrome\BLBeacon").version',
        r'(Get-ItemProperty -Path Registry::"HKLM\SOFTWARE\Wow6432Node\Microsoft\Windows\CurrentVersion\Uninstall\Google Chrome").version',
    ],
}
VERSION_CAMMAND_RE = _compile(r"\d+\.\d+\.\d+")
DRIVER_FILENAME_RE = _compile(r"filename=(.+)")
MAC_SP_VERION_M1 = _parse_version("106.0.5249.61")
