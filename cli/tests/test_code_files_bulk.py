"""Bulk helper-path tests for tools/code.py and tools/files.py."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from models.llm import LLMResponse


@pytest.fixture
def mock_session(tmp_path):
    session = MagicMock()
    session.config.get.side_effect = lambda key, default=None: {
        "sandbox.timeout": 5,
        "sandbox.output_dir": str(tmp_path / "outputs"),
        "sandbox.max_retries": 1,
    }.get(key, default)
    session.console.status.return_value.__enter__ = MagicMock()
    session.console.status.return_value.__exit__ = MagicMock()
    return session


class TestCodeHelpers:
    def test_is_script_authoring_goal_detects_py_target(self):
        from tools.code import _is_script_authoring_goal

        assert _is_script_authoring_goal("Write a python script saved as analysis.py")
        assert not _is_script_authoring_goal("compute mean expression")

    def test_extract_script_filename_from_quotes(self):
        from tools.code import _extract_script_filename

        assert _extract_script_filename('Save as "my_tool.py"') == "my_tool.py"
        assert _extract_script_filename("no filename here") == "generated_script.py"

    def test_resolve_script_path_rejects_absolute(self, tmp_path, monkeypatch):
        from tools.code import _resolve_script_path

        monkeypatch.chdir(tmp_path)
        path, err = _resolve_script_path("/tmp/evil.py")
        assert path is None
        assert "Absolute" in err

    def test_resolve_script_path_rejects_traversal(self, tmp_path, monkeypatch):
        from tools.code import _resolve_script_path

        monkeypatch.chdir(tmp_path)
        path, err = _resolve_script_path("../outside.py")
        assert path is None
        assert "traversal" in err.lower()

    def test_resolve_script_path_accepts_relative(self, tmp_path, monkeypatch):
        from tools.code import _resolve_script_path

        monkeypatch.chdir(tmp_path)
        path, err = _resolve_script_path("tools/helper.py")
        assert err is None
        assert path.name == "helper.py"

    def test_describe_data_files_lists_cwd_csv(self, tmp_path, monkeypatch):
        from tools.code import _describe_data_files

        monkeypatch.chdir(tmp_path)
        (tmp_path / "data.csv").write_text("a,b\n1,2\n")
        desc = _describe_data_files()
        assert "data.csv" in desc

    def test_describe_data_files_extra_dir(self, tmp_path, monkeypatch):
        from tools.code import _describe_data_files

        monkeypatch.chdir(tmp_path)
        extra = tmp_path / "capsule"
        extra.mkdir()
        (extra / "matrix.tsv").write_text("x\ty\n")
        desc = _describe_data_files(extra_dirs=[extra])
        assert "matrix.tsv" in desc

    def test_describe_data_files_empty(self, tmp_path, monkeypatch):
        from tools.code import _describe_data_files

        monkeypatch.chdir(tmp_path)
        assert "No data files" in _describe_data_files()

    @patch("tools.code._generate_and_execute_code")
    def test_execute_non_script_goal_uses_sandbox(self, mock_exec, mock_session):
        from tools.code import execute

        mock_exec.return_value = {"summary": "done", "error": None}
        result = execute(goal="compute correlation matrix", _session=mock_session)
        assert result["summary"] == "done"
        mock_exec.assert_called_once()


class TestFilesHelpers:
    def test_allowed_paths_includes_home_and_config(self, tmp_path):
        from tools.files import _allowed_paths

        cfg = MagicMock()
        cfg.get.side_effect = lambda key, default=None: {
            "sandbox.output_dir": str(tmp_path / "outputs"),
            "data.base": str(tmp_path / "data"),
        }.get(key, default)
        paths = _allowed_paths(cfg)
        assert any("fastfold-cli" in str(p) for p in paths)
        assert tmp_path / "outputs" in paths or (tmp_path / "outputs").parent in paths

    def test_output_dir_from_config(self, tmp_path):
        from tools.files import _output_dir

        cfg = MagicMock()
        cfg.get.return_value = str(tmp_path / "custom_out")
        out = _output_dir(cfg)
        assert out == tmp_path / "custom_out"
        assert out.exists()

    def test_resolve_output_path_rejects_traversal(self, tmp_path):
        from tools.files import _resolve_output_path

        out_dir = tmp_path / "outputs"
        out_dir.mkdir()
        path, err = _resolve_output_path(out_dir, "../escape.md")
        assert path is None
        assert "traversal" in err.lower()

    def test_resolve_output_path_accepts_nested(self, tmp_path):
        from tools.files import _resolve_output_path

        out_dir = tmp_path / "outputs"
        out_dir.mkdir()
        path, err = _resolve_output_path(out_dir, "reports/run.md")
        assert err is None
        assert path.name == "run.md"

    def test_resolve_cwd_path_blocks_outside(self, tmp_path, monkeypatch):
        from tools.files import _resolve_cwd_path

        monkeypatch.chdir(tmp_path)
        path, err = _resolve_cwd_path("/etc/passwd")
        assert path is None
        assert err == "path_not_allowed"

    def test_is_protected_blocks_env_and_git(self, tmp_path):
        from tools.files import _is_protected

        assert _is_protected(Path("/repo/.git/config"))
        assert _is_protected(Path("/home/user/project/.env"))

    def test_is_protected_allows_ssh_pub(self, tmp_path):
        from tools.files import _is_protected

        assert _is_protected(Path("/home/user/.ssh/id_rsa.pub")) is False

    def test_is_allowed_under_output_dir(self, tmp_path):
        from tools.files import _is_allowed

        out = tmp_path / "outputs"
        out.mkdir()
        cfg = MagicMock()
        cfg.get.return_value = str(out)
        assert _is_allowed(out / "report.md", cfg) is True

    def test_extract_archive_zip(self, tmp_path, monkeypatch):
        import zipfile
        from tools.files import extract_archive

        monkeypatch.chdir(tmp_path)
        archive = tmp_path / "bundle.zip"
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr("inner.txt", "hello")
        dest = tmp_path / "extracted"
        result = extract_archive(path=str(archive), destination=str(dest))
        assert "error" not in result
        assert (dest / "inner.txt").read_text() == "hello"
