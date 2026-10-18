"""Platform label, RAM, and thermal helpers used by the status page."""

from __future__ import annotations

import subprocess
from types import SimpleNamespace

from agent_server.status_service import host_metrics as hm


def _run(stdout: str, code: int = 0):
    def inner(cmd, **kwargs):
        return SimpleNamespace(returncode=code, stdout=stdout, stderr="")

    return inner


def test_hw_model_and_product_family(monkeypatch):
    monkeypatch.setattr(hm.platform, "system", lambda: "Linux")
    assert hm._hw_model() is None
    monkeypatch.setattr(hm.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(hm.subprocess, "run", _run("Macmini9,1\n"))
    assert hm._hw_model() == "Macmini9,1"
    monkeypatch.setattr(hm.subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(OSError("no")))
    assert hm._hw_model() is None

    assert hm._mac_product_family("MacBookPro18,3") == "MacBook Pro"
    assert hm._mac_product_family("MacBookAir10,1") == "MacBook Air"
    assert hm._mac_product_family("MacBook10,1") == "MacBook"
    assert hm._mac_product_family("MacPro7,1") == "Mac Pro"
    assert hm._mac_product_family("MacStudio1,1") == "Mac Studio"
    assert hm._mac_product_family("iMacPro1,1") == "iMac Pro"
    assert hm._mac_product_family("iMac21,1") == "iMac"
    assert hm._mac_product_family("VirtualMac2,1") == "Virtual Mac"
    monkeypatch.setattr(
        hm.subprocess,
        "run",
        _run("Hardware:\n      Model Name: Mac mini\n"),
    )
    assert hm._mac_product_family("Mac14,3") == "Mac mini"
    monkeypatch.setattr(hm.subprocess, "run", _run("", code=1))
    assert hm._mac_product_family(None) is None


def test_platform_and_device_labels(monkeypatch):
    monkeypatch.setattr(hm.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(hm.platform, "mac_ver", lambda: ("15.1", ("", "", ""), ""))
    monkeypatch.setattr(hm.platform, "machine", lambda: "arm64")
    assert hm._format_platform_label() == "Apple Silicon · macOS 15.1"
    monkeypatch.setattr(hm.platform, "machine", lambda: "x86_64")
    assert "Intel" in hm._format_platform_label()
    assert hm._format_platform_label(chip_name="M4") == "M4 · macOS 15.1"
    monkeypatch.setattr(hm, "_hw_model", lambda: "Macmini9,1")
    assert hm.format_device_label(chip_name="M4").startswith("Mac mini · ")
    monkeypatch.setattr(hm, "_hw_model", lambda: None)
    monkeypatch.setattr(hm, "_mac_product_family", lambda _model: None)
    assert hm.format_device_label() == hm._format_platform_label()

    monkeypatch.setattr(hm.platform, "system", lambda: "Linux")
    monkeypatch.setattr(hm.platform, "release", lambda: "6.8")
    monkeypatch.setattr(hm.platform, "machine", lambda: "aarch64")
    assert hm._format_platform_label() == "Linux · ARM64"
    assert hm.format_device_label() == "Linux · ARM64"
    monkeypatch.setattr(hm.platform, "system", lambda: "Windows")
    monkeypatch.setattr(hm.platform, "machine", lambda: "AMD64")
    assert hm._format_platform_label() == "Windows · AMD64"


def test_ram_thermal_and_load(monkeypatch, tmp_path):
    monkeypatch.setattr(hm.platform, "system", lambda: "Darwin")

    def darwin_run(cmd, **kwargs):
        if cmd[0] == "sysctl":
            return SimpleNamespace(returncode=0, stdout="17179869184\n", stderr="")
        return SimpleNamespace(
            returncode=0,
            stdout="Mach Virtual Memory Statistics: (page size of 16384 bytes)\nPages active: 10.\nPages wired down: 2.\nPages occupied by compressor: 1.\n",
            stderr="",
        )

    monkeypatch.setattr(hm.subprocess, "run", darwin_run)
    used, total = hm._ram_bytes()
    assert total == 17179869184
    assert used == 13 * 16384

    monkeypatch.setattr(hm.platform, "system", lambda: "Linux")
    mem = tmp_path / "meminfo"
    mem.write_text("MemTotal: 1000 kB\nMemAvailable: 400 kB\n", encoding="utf-8")
    monkeypatch.setattr(hm.Path, "read_text", lambda self, encoding="utf-8": mem.read_text())
    # Path("/proc/meminfo") is a real Path; patch read via the instance method on the class
    # only when the path matches.
    real = hm.Path.read_text

    def read_text(self, encoding="utf-8"):
        if self.name == "meminfo":
            return "MemTotal: 1000 kB\nMemAvailable: 400 kB\n"
        return real(self, encoding=encoding)

    monkeypatch.setattr(hm.Path, "read_text", read_text)
    used, total = hm._ram_bytes()
    assert total == 1000 * 1024
    assert used == 600 * 1024

    monkeypatch.setattr(hm.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(
        hm.subprocess,
        "run",
        _run("CPU_Speed_Limit = 80\n"),
    )
    assert hm._thermal_state() == "Fair"
    monkeypatch.setattr(hm.subprocess, "run", _run("Note: No thermal warning\nnominal\n"))
    assert hm._thermal_state() == "Nominal"
    monkeypatch.setattr(hm.subprocess, "run", _run("", code=1))
    assert hm._thermal_state() is None
    monkeypatch.setattr(hm.platform, "system", lambda: "Linux")
    assert hm._thermal_state() is None
    monkeypatch.setattr(hm.os, "getloadavg", lambda: (1.2, 0.5, 0.1))
    assert hm._load_average() == [1.2, 0.5, 0.1]
    monkeypatch.setattr(hm.os, "getloadavg", lambda: (_ for _ in ()).throw(OSError("no")))
    assert hm._load_average() is None
    monkeypatch.setattr(hm.subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(subprocess.TimeoutExpired("x", 1)))
    monkeypatch.setattr(hm.platform, "system", lambda: "Darwin")
    assert hm._ram_bytes() == (0, 0)
