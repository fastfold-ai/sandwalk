"""Edge coverage for workspace reads, store self-heal, and integration mutate."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from agent.config import Config
from agent.doctor.model_provider_http import ModelsProbeResult
from agent_server import store_heal as heal
from agent_server.integrations_service import IntegrationsService
from agent_server.integrations_service import mutate as mutate_mod
from agent_server.workspace import read_mixin
from agent_server.workspace.errors import WorkspacePathError
from agent_server.workspace.read_mixin import WorkspaceReadMixin

_ENV_KEYS = (
    "ANTHROPIC_API_KEY",
    "AWS_ACCESS_KEY_ID",
    "AWS_PROFILE",
    "AWS_REGION",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_SESSION_TOKEN",
    "DASHSCOPE_API_KEY",
    "IBM_RXN_API_KEY",
    "QWEN_API_KEY",
    "QWEN_BASE_URL",
)


class _Reader(WorkspaceReadMixin):
    def __init__(self, root: Path) -> None:
        self.root = root


def _sqlite_db(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE sessions (id TEXT)")
        connection.execute("INSERT INTO sessions (id) VALUES ('s1')")
        connection.commit()
    return path


def _raise_oserror(self, *args, **kwargs):
    raise OSError("boom")


def _raise_valueerror(self, *args, **kwargs):
    raise ValueError("boom")


@pytest.fixture
def isolated_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    for name in _ENV_KEYS:
        monkeypatch.setenv(name, "")
    config_dir = tmp_path / "cfg"
    config_dir.mkdir()
    monkeypatch.setattr("agent.config.CONFIG_DIR", config_dir)
    monkeypatch.setattr("agent.config.CONFIG_FILE", config_dir / "config.json")
    monkeypatch.setattr("agent.config.CONFIG_BACKUP_FILE", config_dir / "config.json.bak")
    Config({}).save()
    return config_dir


def test_resolve_strips_dot_slash_and_rejects_missing(tmp_path: Path) -> None:
    root = tmp_path / "ws"
    root.mkdir()
    (root / "notes.txt").write_text("n", encoding="utf-8")
    reader = _Reader(root)

    resolved = reader.resolve("././notes.txt")
    assert resolved == (root / "notes.txt").resolve()
    with pytest.raises(FileNotFoundError):
        reader.resolve("missing.txt", must_exist=True)


def test_allowed_path_handles_project_mount_failures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "ws"
    root.mkdir()
    reader = _Reader(root)

    with monkeypatch.context() as patch:
        patch.setattr(Path, "is_relative_to", _raise_valueerror)
        with pytest.raises(WorkspacePathError):
            reader.resolve("notes.txt")

    with pytest.raises(WorkspacePathError):
        reader.resolve("project/../../outside.txt")

    linked = tmp_path / "linked"
    linked.mkdir()
    link = root / "project"
    link.symlink_to(linked, target_is_directory=True)
    real_resolve = Path.resolve

    def resolve_link_fails(self: Path, *args, **kwargs):
        if self == link:
            raise OSError("link")
        return real_resolve(self, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(Path, "resolve", resolve_link_fails)
        with pytest.raises(WorkspacePathError):
            reader.resolve("project/../../outside.txt")

    real_relative = Path.is_relative_to

    def relative_to_target_fails(self: Path, other: Path) -> bool:
        if other != root:
            raise OSError("target")
        return real_relative(self, other)

    with monkeypatch.context() as patch:
        patch.setattr(Path, "is_relative_to", relative_to_target_fails)
        with pytest.raises(WorkspacePathError):
            reader.resolve("project/../../outside.txt")


def test_relative_rejects_paths_outside_root_and_project(tmp_path: Path) -> None:
    root = tmp_path / "ws"
    root.mkdir()
    reader = _Reader(root)
    outside = tmp_path / "outside"
    outside.mkdir()

    with pytest.raises(ValueError, match="not inside"):
        reader.relative(outside)

    linked = tmp_path / "linked"
    linked.mkdir()
    (root / "project").symlink_to(linked, target_is_directory=True)
    with pytest.raises(ValueError, match="not inside"):
        reader.relative(outside)


def test_non_recursive_list_skips_unreadable_entries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "ws"
    root.mkdir()
    (root / "keep.txt").write_text("ok", encoding="utf-8")
    (root / "dir").mkdir()
    (root / "node_modules").mkdir()
    (root / "ghost").write_text("g", encoding="utf-8")
    (root / "broken").write_text("b", encoding="utf-8")
    reader = _Reader(root)
    real_relative = reader.relative
    real_stat = Path.stat

    def relative(path: Path) -> str:
        if path.name == "ghost":
            raise ValueError("outside")
        return real_relative(path)

    def stat(self: Path, *args, **kwargs):
        if self.name == "broken":
            raise OSError("stat")
        return real_stat(self, *args, **kwargs)

    monkeypatch.setattr(reader, "relative", relative)
    monkeypatch.setattr(Path, "stat", stat)

    names = {item.name for item in reader.list("", recursive=False)}
    assert names == {"keep.txt", "dir"}


def test_recursive_list_stops_at_budget_and_skips_bad_dirs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "ws"
    root.mkdir()
    (root / "keep.txt").write_text("ok", encoding="utf-8")
    reader = _Reader(root)
    clock = iter((0.0, 10.0))
    monkeypatch.setattr(read_mixin.time, "monotonic", lambda: next(clock))
    assert reader.list("") == []

    def scandir_fails(*args, **kwargs):
        raise OSError("scandir")

    monkeypatch.setattr(read_mixin.time, "monotonic", lambda: 0.0)
    monkeypatch.setattr(read_mixin.os, "scandir", scandir_fails)
    assert reader.list("") == []


def test_recursive_list_skips_stat_failures_cycles_and_symlinks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "ws"
    root.mkdir()
    aaa = root / "aaa"
    aaa.mkdir()
    (aaa / "f.txt").write_text("a", encoding="utf-8")
    (root / "project").symlink_to(aaa, target_is_directory=True)
    library = root / "Library"
    library.mkdir()
    (library / "secret.txt").write_text("s", encoding="utf-8")
    (root / "ghost").write_text("g", encoding="utf-8")
    (root / "brokenstat").write_text("b", encoding="utf-8")
    target = tmp_path / "dest"
    target.mkdir()
    (root / "weirdlink").symlink_to(target, target_is_directory=True)

    reader = _Reader(root)
    real_relative = WorkspaceReadMixin.relative
    real_dir_stat = os.DirEntry.stat
    real_resolve = Path.resolve
    real_path_stat = Path.stat
    root_stats = {"n": 0}

    def relative(self, path: Path) -> str:
        if Path(path).name == "ghost":
            raise ValueError("outside")
        return real_relative(self, path)

    def dir_stat(self, *args, **kwargs):
        if self.name == "brokenstat":
            raise OSError("stat")
        return real_dir_stat(self, *args, **kwargs)

    def resolve(self: Path, *args, **kwargs):
        if self.name == "weirdlink":
            raise OSError("resolve")
        return real_resolve(self, *args, **kwargs)

    def path_stat(self: Path, *args, **kwargs):
        if self == root:
            root_stats["n"] += 1
            if root_stats["n"] > 2:
                raise OSError("dev")
        return real_path_stat(self, *args, **kwargs)

    monkeypatch.setattr(WorkspaceReadMixin, "relative", relative)
    monkeypatch.setattr(os.DirEntry, "stat", dir_stat)
    monkeypatch.setattr(Path, "resolve", resolve)
    listed = reader.list("")
    paths = {item.path for item in listed}
    assert "aaa/f.txt" in paths
    assert "project" in paths
    assert "project/f.txt" not in paths
    assert "ghost" not in paths
    assert "brokenstat" not in paths
    assert "weirdlink" in paths
    assert reader.list("Library") == []

    monkeypatch.setattr(Path, "stat", path_stat)
    assert reader.list("") == []


def test_read_directory_invalid_text_and_binary(tmp_path: Path) -> None:
    root = tmp_path / "ws"
    root.mkdir()
    (root / "folder").mkdir()
    (root / "bad.txt").write_bytes(b"\xff\xfe not utf-8")
    (root / "blob.bin").write_bytes(b"\x00\x01\x02")
    reader = _Reader(root)

    with pytest.raises(NotADirectoryError):
        reader.list("bad.txt")
    with pytest.raises(IsADirectoryError):
        reader.read("folder")
    text = reader.read("bad.txt")
    assert text.encoding == "base64"
    blob = reader.read("blob.bin")
    assert blob.encoding == "base64"
    assert blob.mime_type == "application/octet-stream"


def test_integrity_and_readonly_probes_treat_unknown_as_not_broken(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = tmp_path / "agent.db"
    db.write_bytes(b"not-empty")

    def connect_fails(*args, **kwargs):
        raise sqlite3.DatabaseError("malformed")

    monkeypatch.setattr(heal.sqlite3, "connect", connect_fails)
    assert heal.integrity_ok(db) is False
    assert heal.data_volume(db) is None

    class Locked:
        def execute(self, *args, **kwargs):
            raise sqlite3.OperationalError("locked")

        def close(self) -> None:
            return None

    monkeypatch.setattr(heal.sqlite3, "connect", lambda *args, **kwargs: Locked())
    assert heal.readonly_readable(db) is None
    assert heal.readonly_integrity_ok(db) is None


def test_restore_rejects_backup_that_fails_after_install(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    backup = _sqlite_db(tmp_path / "backup.db")
    dest = tmp_path / "restored.db"
    checks = {"n": 0}

    def integrity(path: Path, isolate_main: bool = False) -> bool:
        checks["n"] += 1
        return checks["n"] == 1

    monkeypatch.setattr(heal, "integrity_ok", integrity)
    assert heal.restore_from_backup(dest, backup) is False
    assert dest.exists()


def test_refresh_backup_handles_meta_and_snapshot_failures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = _sqlite_db(tmp_path / "agent.db")
    real_integrity = heal.integrity_ok
    assert heal.refresh_healthy_backup(db, force=True) is True
    meta = Path(f"{heal.backup_path_for(db)}.fp")
    assert meta.exists()
    real_read = Path.read_text

    def read_text(self: Path, *args, **kwargs):
        if self == meta:
            raise OSError("meta")
        return real_read(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", read_text)
    assert heal.refresh_healthy_backup(db, force=False) is True

    def integrity(path: Path, isolate_main: bool = False) -> bool:
        return not path.name.endswith(".tmp")

    monkeypatch.setattr(heal, "integrity_ok", integrity)
    assert heal.refresh_healthy_backup(db, force=True) is None

    real_write = Path.write_text

    def write_text(self: Path, *args, **kwargs):
        if self.name.endswith(".fp"):
            raise OSError("write")
        return real_write(self, *args, **kwargs)

    monkeypatch.setattr(heal, "integrity_ok", real_integrity)
    monkeypatch.setattr(Path, "write_text", write_text)
    assert heal.refresh_healthy_backup(db, force=True) is True
    assert not meta.exists()

    real_connect = sqlite3.connect

    def connect(*args, **kwargs):
        target = args[0] if args else ""
        if isinstance(target, str) and "mode=ro" in target:
            return real_connect(*args, **kwargs)
        raise sqlite3.DatabaseError("backup")

    monkeypatch.setattr(heal.sqlite3, "connect", connect)
    assert heal.refresh_healthy_backup(db, force=True) is None


def test_prune_survives_unlink_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db = tmp_path / "agent.db"
    db.write_bytes(b"db")
    for index in range(2):
        db.with_name(f"{db.name}.corrupt-2020010{index}-000000").write_text("q", encoding="utf-8")

    real_unlink = Path.unlink

    def unlink(self: Path, *args, **kwargs):
        if ".corrupt-" in self.name:
            raise OSError("busy")
        return real_unlink(self, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", unlink)
    assert heal.prune_quarantines(db, keep=0) == 2


def test_orphan_target_avoids_existing_names(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = tmp_path / "agent.db"
    stamp = "20200101-000000"
    monkeypatch.setattr(heal.time, "strftime", lambda fmt: stamp)
    taken = db.with_name(f"{db.name}.orphan-{stamp}-wal")
    taken.write_text("wal", encoding="utf-8")
    target = heal._orphan_target(db, "-wal")
    assert target.name == f"{db.name}.orphan-{stamp}-1-wal"


def test_repair_rolls_back_when_sidecar_move_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = _sqlite_db(tmp_path / "agent.db")
    wal = Path(f"{db}-wal")
    shm = Path(f"{db}-shm")
    wal.write_bytes(b"wal")
    shm.write_bytes(b"shm")
    monkeypatch.setattr(heal, "readonly_integrity_ok", lambda path: False)
    monkeypatch.setattr(heal, "integrity_ok", lambda path, isolate_main=False: True)
    moves = {"n": 0}
    real_replace = Path.replace

    def replace(self: Path, dest: Path):
        moves["n"] += 1
        if moves["n"] == 2:
            raise OSError("replace")
        return real_replace(self, dest)

    monkeypatch.setattr(Path, "replace", replace)
    assert heal.repair_mismatched_sidecars(db) is None
    assert wal.exists()
    assert shm.exists()


def test_repair_restores_sidecars_when_main_is_still_bad(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db = _sqlite_db(tmp_path / "agent.db")
    wal = Path(f"{db}-wal")
    shm = Path(f"{db}-shm")
    wal.write_bytes(b"wal")
    shm.write_bytes(b"shm")
    monkeypatch.setattr(heal, "readonly_integrity_ok", lambda path: False)

    def integrity(path: Path, isolate_main: bool = False) -> bool:
        return isolate_main is True

    monkeypatch.setattr(heal, "integrity_ok", integrity)
    assert heal.repair_mismatched_sidecars(db) is None
    assert wal.read_bytes() == b"wal"
    assert shm.read_bytes() == b"shm"


def test_attempt_self_heal_branches(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SANDWALK_DB_AUTO_HEAL", "1")
    db = tmp_path / "agent.db"
    db.write_bytes(b"corrupt")
    monkeypatch.setattr(heal, "repair_mismatched_sidecars", lambda path: "sidecar fixed")
    assert heal.attempt_self_heal(db, detail="malformed") == "sidecar fixed"

    monkeypatch.setattr(heal, "repair_mismatched_sidecars", lambda path: None)
    missing = tmp_path / "missing.db"
    with pytest.raises(RuntimeError, match="path missing"):
        heal.attempt_self_heal(missing, detail="malformed")

    def recover_ok(source: Path, dest: Path) -> bool:
        dest.write_bytes(b"recovered")
        return True

    monkeypatch.setattr(heal, "recover_via_sqlite_cli", recover_ok)
    monkeypatch.setattr(heal, "replacement_loses_data", lambda current, candidate: "1 of 10 rows")
    with pytest.raises(RuntimeError, match="Refusing to repair"):
        heal.attempt_self_heal(db, detail="malformed")

    monkeypatch.setattr(heal, "replacement_loses_data", lambda current, candidate: None)
    monkeypatch.setattr(heal, "prune_quarantines", lambda path, keep=5: 0)
    monkeypatch.setattr(heal, "refresh_healthy_backup", lambda path, force=True: True)
    note = heal.attempt_self_heal(db, detail="malformed")
    assert "sqlite3 .recover" in note
    assert db.read_bytes() == b"recovered"

    monkeypatch.setattr(heal, "recover_via_sqlite_cli", lambda source, dest: False)
    monkeypatch.setattr(
        heal, "replacement_loses_data", lambda current, candidate: "0 of 10 rows"
    )
    with pytest.raises(RuntimeError, match="Refusing to restore"):
        heal.attempt_self_heal(db, detail="malformed")

    monkeypatch.setattr(heal, "replacement_loses_data", lambda current, candidate: None)
    monkeypatch.setattr(heal, "restore_from_backup", lambda path, backup: False)
    with pytest.raises(RuntimeError, match="no healthy backup"):
        heal.attempt_self_heal(db, detail="malformed")


@pytest.mark.parametrize(
    ("probe", "label"),
    [
        (mutate_mod._probe_boltz_api_key, "Boltz"),
        (mutate_mod._probe_fastfold_api_key, "Fastfold"),
        (mutate_mod._probe_vercel_skills_token, "skills.sh"),
        (mutate_mod._probe_huggingface_token, "Hugging Face"),
    ],
)
def test_provider_probes_report_network_and_http_failures(
    monkeypatch: pytest.MonkeyPatch, probe, label: str
) -> None:
    def offline(*args, **kwargs):
        raise TimeoutError("offline")

    monkeypatch.setattr(mutate_mod.httpx, "get", offline)
    ok, message = probe("token")
    assert ok is False
    assert label in message

    def http_500(*args, **kwargs):
        return MagicMock(status_code=500)

    monkeypatch.setattr(mutate_mod.httpx, "get", http_500)
    ok, message = probe("token")
    assert ok is False
    assert "500" in message


def test_huggingface_probe_ignores_unreadable_whoami(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def bad_json(*args, **kwargs):
        response = MagicMock(status_code=200)
        response.json.side_effect = ValueError("not json")
        return response

    monkeypatch.setattr(mutate_mod.httpx, "get", bad_json)
    ok, message = mutate_mod._probe_huggingface_token("hf_token")
    assert ok is True
    assert message == "Hugging Face token works."


def test_update_skips_unknown_fields_and_clears_blank_endpoint(
    isolated_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("QWEN_BASE_URL", "https://stale.example/v1")
    updated = IntegrationsService().update(
        "qwen",
        {
            "UNKNOWN_FIELD": "skip",
            "QWEN_API_KEY": "sk-qwen-test",
            "QWEN_BASE_URL": "   ",
        },
    )
    assert updated.configured is True
    assert os.environ["QWEN_API_KEY"] == "sk-qwen-test"
    assert os.environ["DASHSCOPE_API_KEY"] == "sk-qwen-test"
    assert "QWEN_BASE_URL" not in os.environ
    assert Config.load().get("llm.qwen_api_key") == "sk-qwen-test"
    assert not str(Config.load().get("llm.qwen_base_url") or "").strip()

    IntegrationsService().update(
        "qwen",
        {"QWEN_BASE_URL": "https://dashscope.aliyuncs.com"},
    )
    assert (
        Config.load().get("llm.qwen_base_url")
        == "https://dashscope.aliyuncs.com/compatible-mode/v1"
    )


def test_remove_unknown_and_bedrock_resets_region(isolated_config: Path) -> None:
    service = IntegrationsService()
    with pytest.raises(KeyError):
        service.remove("not-a-provider")

    config = Config.load()
    config.set("llm.aws_region", "eu-west-1")
    config.set("llm.bedrock_verified", True)
    config.set("llm.aws_access_key_id", "AKIA_TEST")
    config.save()
    removed = service.remove("bedrock")
    assert removed.configured is False
    loaded = Config.load()
    assert loaded.get("llm.aws_region") == "us-east-1"
    assert loaded.get("llm.bedrock_verified") is False
    assert not loaded.get("llm.aws_access_key_id")


def test_secret_value_prefers_config_then_env(
    isolated_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = IntegrationsService()
    assert service._secret_value("not-a-provider") == ""

    config = Config.load()
    config.set("llm.qwen_base_url", "https://example.invalid/v1")
    config.save()
    assert service._secret_value("qwen") == ""

    config = Config.load()
    config.set("llm.anthropic_api_key", "sk-from-config")
    config.save()
    assert service._secret_value("anthropic") == "sk-from-config"

    class EmptyConfig:
        def get(self, key: str, default=None):
            return None

    monkeypatch.setattr(mutate_mod.Config, "load", lambda: EmptyConfig())
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-from-env")
    assert service._secret_value("anthropic") == "sk-from-env"


def test_reveal_secret_rejects_unknown_provider(isolated_config: Path) -> None:
    with pytest.raises(KeyError):
        IntegrationsService().reveal_secret("not-a-provider")


def test_validate_persists_qwen_endpoint_and_bedrock_flag(
    isolated_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("QWEN_API_KEY", "sk-qwen-test")

    def qwen_probe(key: str, secret: str, label: str | None = None) -> ModelsProbeResult:
        return ModelsProbeResult(
            ok=False,
            message="found host",
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )

    monkeypatch.setattr(mutate_mod, "probe_llm_api_key", qwen_probe)
    result = IntegrationsService().validate("qwen")
    assert result.ok is False
    assert (
        Config.load().get("llm.qwen_base_url")
        == "https://dashscope.aliyuncs.com/compatible-mode/v1"
    )

    def bedrock_probe(key: str, secret: str, label: str | None = None) -> ModelsProbeResult:
        return ModelsProbeResult(ok=True, message="Bedrock works.")

    monkeypatch.setattr(mutate_mod, "probe_llm_api_key", bedrock_probe)
    monkeypatch.setattr(
        "agent_server.models_service.mutate.enable_models_for_provider",
        lambda config, key: ["bedrock:model"],
    )
    result = IntegrationsService().validate("bedrock")
    assert result.ok is True
    assert Config.load().get("llm.bedrock_verified") is True


def test_validate_configured_non_llm_provider(isolated_config: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IBM_RXN_API_KEY", "ibm-test-key")
    result = IntegrationsService().validate("ibm-rxn")
    assert result.ok is True
    assert result.configured is True
    assert "IBM RXN" in result.message
