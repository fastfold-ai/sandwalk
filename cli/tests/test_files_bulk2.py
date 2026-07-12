"""Additional bulk tests for tools/files.py archive and binary read paths."""

import tarfile
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from tools.files import extract_archive, list_directory, read_file


@pytest.fixture
def mock_session(tmp_path, monkeypatch):
    session = MagicMock()
    session.config.get.side_effect = lambda key, default=None: {
        "sandbox.output_dir": str(tmp_path / "outputs"),
        "data.base": str(tmp_path / "data"),
        "sandbox.extra_read_dirs": str(tmp_path / "capsule"),
    }.get(key, default)
    return session


class TestExtractArchive:
    def test_extract_zip_with_pattern(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        archive = tmp_path / "bundle.zip"
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr("keep.txt", "ok")
            zf.writestr("skip.log", "nope")

        result = extract_archive(str(archive), destination="extracted", pattern="*.txt")
        assert result["extracted_count"] == 1
        assert (tmp_path / "extracted" / "keep.txt").exists()

    def test_extract_tar_archive(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        archive = tmp_path / "bundle.tar.gz"
        with tarfile.open(archive, "w:gz") as tf:
            data = b"hello"
            info = tarfile.TarInfo(name="inner.txt")
            info.size = len(data)
            tf.addfile(info, fileobj=__import__("io").BytesIO(data))

        result = extract_archive(str(archive), destination="tar_out")
        assert result["extracted_count"] >= 1
        assert (tmp_path / "tar_out" / "inner.txt").exists()

    def test_extract_archive_not_found(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = extract_archive("missing.zip")
        assert result["error"] == "file_not_found"

    def test_extract_unsupported_format(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        path = tmp_path / "file.rar"
        path.write_bytes(b"fake")
        result = extract_archive(str(path))
        assert result["error"] == "unsupported_format"

    def test_extract_from_extra_read_dir(self, tmp_path, monkeypatch, mock_session):
        monkeypatch.chdir(tmp_path)
        capsule = tmp_path / "capsule"
        capsule.mkdir()
        archive = capsule / "remote.zip"
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr("data.csv", "a,b\n1,2\n")

        result = extract_archive("remote.zip", destination="out", _session=mock_session)
        assert result["extracted_count"] == 1


class TestReadFileBinaryFormats:
    def test_read_excel_preview(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        xlsx = tmp_path / "table.xlsx"
        pd.DataFrame({"gene": ["TP53"], "value": [1.0]}).to_excel(xlsx, index=False)

        result = read_file(path=str(xlsx))
        assert result.get("format") == "excel"
        assert "TP53" in str(result.get("preview"))

    def test_read_binary_non_excel(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        binary = tmp_path / "blob.bin"
        binary.write_bytes(bytes([0xFF, 0xFE, 0xFD]))

        result = read_file(path=str(binary))
        assert result.get("error") == "binary_file" or "binary" in result["summary"].lower()


class TestListDirectoryExtended:
    def test_list_directory_recursive_hidden(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".hidden").write_text("secret")
        (tmp_path / "visible.txt").write_text("ok")
        sub = tmp_path / "nested"
        sub.mkdir()
        (sub / "child.txt").write_text("child")

        result = list_directory(path=str(tmp_path), recursive=True, show_hidden=True, max_entries=10)
        assert result["count"] >= 3
        names = {entry["name"] for entry in result["entries"]}
        assert ".hidden" in names

    def test_list_directory_outside_cwd_denied(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        outside = tmp_path.parent / "outside_list"
        outside.mkdir(exist_ok=True)
        result = list_directory(path=str(outside))
        assert result["error"] == "path_not_allowed"
