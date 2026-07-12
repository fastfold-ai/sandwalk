"""Tests for api.config dataset discovery and schema validation."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import api.config as config_mod


class TestDiscoverDatasets:
    def test_discovers_available_dataset(self, tmp_path, monkeypatch):
        data_dir = tmp_path / "perturbatlas" / "Homo sapiens" / "exp1"
        data_dir.mkdir(parents=True)
        (data_dir / "degs.csv.gz").write_bytes(b"gene,log2FoldChange\n")

        monkeypatch.setattr(config_mod, "DATA_ROOT", tmp_path)
        available = config_mod.discover_datasets()
        assert "perturbatlas" in available
        assert available["perturbatlas"]["n_files"] >= 1

    def test_empty_when_no_files(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config_mod, "DATA_ROOT", tmp_path)
        assert config_mod.discover_datasets() == {}


class TestValidateSchema:
    def test_unavailable_dataset(self, tmp_path, monkeypatch):
        monkeypatch.setattr(config_mod, "DATA_ROOT", tmp_path)
        engine = MagicMock()
        results = config_mod.validate_schema(engine)
        assert results["perturbatlas"]["status"] == "unavailable"

    def test_valid_schema(self, tmp_path, monkeypatch):
        data_dir = tmp_path / "perturbatlas" / "Homo sapiens" / "exp1"
        data_dir.mkdir(parents=True)
        (data_dir / "degs.csv.gz").write_bytes(b"x")

        monkeypatch.setattr(config_mod, "DATA_ROOT", tmp_path)
        engine = MagicMock()
        engine.sample_columns.return_value = [
            "column0", "perturb_id", "gene", "baseMean", "log2FoldChange",
            "lfcSE", "stat", "pvalue", "padj",
        ]
        results = config_mod.validate_schema(engine)
        assert results["perturbatlas"]["status"] == "valid"

    def test_invalid_missing_required(self, tmp_path, monkeypatch):
        data_dir = tmp_path / "perturbatlas" / "Homo sapiens" / "exp1"
        data_dir.mkdir(parents=True)
        (data_dir / "degs.csv.gz").write_bytes(b"x")

        monkeypatch.setattr(config_mod, "DATA_ROOT", tmp_path)
        engine = MagicMock()
        engine.sample_columns.return_value = ["gene"]
        results = config_mod.validate_schema(engine)
        assert results["perturbatlas"]["status"] == "invalid"
