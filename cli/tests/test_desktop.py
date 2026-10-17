"""Asset selection for `sandwalk desktop`."""

import pytest

from cli.desktop import DesktopInstallError, select_desktop_asset

ASSETS = [
    {"name": "Sandwalk-0.1.10-macos-arm64.dmg", "browser_download_url": "https://example/ver.dmg"},
    {"name": "Sandwalk-macos-arm64.dmg", "browser_download_url": "https://example/mac.dmg"},
    {"name": "Sandwalk_0.1.10_amd64.deb", "browser_download_url": "https://example/amd64.deb"},
    {"name": "Sandwalk_0.1.10_arm64.deb", "browser_download_url": "https://example/arm64.deb"},
]


def test_mac_selects_the_stable_dmg_name():
    asset = select_desktop_asset(ASSETS, system="Darwin", machine="arm64")
    assert asset["name"] == "Sandwalk-macos-arm64.dmg"


def test_linux_selects_the_deb_for_the_cpu():
    amd = select_desktop_asset(ASSETS, system="Linux", machine="x86_64")
    arm = select_desktop_asset(ASSETS, system="Linux", machine="aarch64")
    assert amd["name"].endswith("_amd64.deb")
    assert arm["name"].endswith("_arm64.deb")


def test_intel_mac_is_refused():
    with pytest.raises(DesktopInstallError, match="Apple Silicon"):
        select_desktop_asset(ASSETS, system="Darwin", machine="x86_64")


def test_unknown_system_is_refused():
    with pytest.raises(DesktopInstallError, match="Windows"):
        select_desktop_asset(ASSETS, system="Windows", machine="x86_64")
