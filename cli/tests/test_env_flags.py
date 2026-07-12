"""Tests for optional integration/smoke env flag helpers."""

import os

import pytest

from env_flags import env_flag, env_value


@pytest.mark.parametrize(
    "value",
    ["1", "true", "TRUE", " yes ", "Yes"],
)
def test_env_flag_truthy(value, monkeypatch):
    monkeypatch.delenv("RUN_API_SMOKE", raising=False)
    monkeypatch.setenv("RUN_API_SMOKE", value)
    assert env_flag("RUN_API_SMOKE", "CT_RUN_API_SMOKE") is True


@pytest.mark.parametrize("value", ["", "0", "false", "no"])
def test_env_flag_falsy(value, monkeypatch):
    monkeypatch.delenv("RUN_API_SMOKE", raising=False)
    monkeypatch.delenv("CT_RUN_API_SMOKE", raising=False)
    if value:
        monkeypatch.setenv("RUN_API_SMOKE", value)
    assert env_flag("RUN_API_SMOKE", "CT_RUN_API_SMOKE") is False


def test_env_flag_legacy_ct_name(monkeypatch):
    monkeypatch.delenv("RUN_API_SMOKE", raising=False)
    monkeypatch.setenv("CT_RUN_API_SMOKE", "1")
    assert env_flag("RUN_API_SMOKE", "CT_RUN_API_SMOKE") is True


def test_env_value_prefers_first_set(monkeypatch):
    monkeypatch.setenv("API_SMOKE_STRICT", "strict")
    monkeypatch.setenv("CT_API_SMOKE_STRICT", "legacy")
    assert env_value("API_SMOKE_STRICT", "CT_API_SMOKE_STRICT") == "strict"


def test_env_value_falls_back_to_second_name(monkeypatch):
    monkeypatch.delenv("API_SMOKE_STRICT", raising=False)
    monkeypatch.setenv("CT_API_SMOKE_STRICT", "legacy")
    assert env_value("API_SMOKE_STRICT", "CT_API_SMOKE_STRICT") == "legacy"


def test_env_value_default(monkeypatch):
    monkeypatch.delenv("API_SMOKE_STRICT", raising=False)
    monkeypatch.delenv("CT_API_SMOKE_STRICT", raising=False)
    assert env_value("API_SMOKE_STRICT", "CT_API_SMOKE_STRICT", default="off") == "off"
