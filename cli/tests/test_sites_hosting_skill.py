"""Focused tests for the bundled sites-hosting skill and packager."""

from __future__ import annotations

import importlib.util
import json
import sys
import zipfile
from pathlib import Path

import pytest

SKILL = Path(__file__).parents[1] / "src" / "skills" / "sites_hosting"
SCRIPT = SKILL / "scripts" / "package_site.py"
SPEC = importlib.util.spec_from_file_location("sites_hosting_package_site", SCRIPT)
assert SPEC and SPEC.loader
package_site = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = package_site
SPEC.loader.exec_module(package_site)


def _dist(tmp_path: Path) -> Path:
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<h1>Site</h1>\n", encoding="utf-8")
    (dist / "assets" / "app.js").write_text("console.log('site')\n", encoding="utf-8")
    return dist


def test_skill_metadata_and_publish_guardrails():
    text = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    assert "name: sites-hosting" in text
    assert "author: sandwalk" in text
    assert "category: Built-in" in text
    assert "version: 1.0.0" in text
    assert "FASTFOLD_API_KEY" in text
    assert "sites.manage" in text
    assert "<slug>.sandwalk.site" in text
    assert "Never say deployed" in text
    assert len(text.splitlines()) < 500


def test_package_is_deterministic_and_exact(tmp_path):
    dist = _dist(tmp_path)
    first = tmp_path / "first.zip"
    first_manifest = tmp_path / "first.manifest.json"
    second = tmp_path / "second.zip"
    second_manifest = tmp_path / "second.manifest.json"

    manifest = package_site.package(dist, first, first_manifest)
    package_site.package(dist, second, second_manifest)

    assert first.read_bytes() == second.read_bytes()
    assert first_manifest.read_bytes() == second_manifest.read_bytes()
    assert [entry["path"] for entry in manifest["files"]] == ["assets/app.js", "index.html"]
    with zipfile.ZipFile(first) as bundle:
        assert bundle.namelist() == ["assets/app.js", "index.html"]
    assert package_site.validate_package(first, first_manifest) == manifest


@pytest.mark.parametrize(
    "relative",
    [
        ".env",
        "assets/.hidden",
        "credentials.json",
        "private-key.pem",
        "assets/api_key.txt",
    ],
)
def test_package_rejects_dotfiles_and_secrets(tmp_path, relative):
    dist = _dist(tmp_path)
    target = dist / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("private", encoding="utf-8")

    with pytest.raises(package_site.PackageError):
        package_site.package(dist, tmp_path / "site.zip", tmp_path / "manifest.json")


def test_package_rejects_symlinks(tmp_path):
    dist = _dist(tmp_path)
    (dist / "linked.js").symlink_to(dist / "assets" / "app.js")

    with pytest.raises(package_site.PackageError, match="symlinks"):
        package_site.build_manifest(dist)


@pytest.mark.parametrize("name", ["../escape.txt", "/absolute.txt", r"assets\\escape.txt"])
def test_archive_validation_rejects_unsafe_paths(tmp_path, name):
    archive = tmp_path / "unsafe.zip"
    manifest_path = tmp_path / "manifest.json"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_STORED) as bundle:
        info = zipfile.ZipInfo(name, date_time=package_site._TIMESTAMP)
        bundle.writestr(info, b"x")
    manifest_path.write_text(
        json.dumps(
            {
                "expanded_bytes": 1,
                "file_count": 1,
                "files": [{"bytes": 1, "path": name, "sha256": "0" * 64}],
                "format": "sandwalk-sites-manifest",
                "version": 1,
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(package_site.PackageError):
        package_site.validate_package(archive, manifest_path)


def test_validation_rejects_manifest_drift(tmp_path):
    dist = _dist(tmp_path)
    archive = tmp_path / "site.zip"
    manifest_path = tmp_path / "manifest.json"
    package_site.package(dist, archive, manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"][0]["sha256"] = "0" * 64
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(package_site.PackageError, match="exactly match"):
        package_site.validate_package(archive, manifest_path)


def test_limits_and_outputs_inside_dist_are_rejected(tmp_path, monkeypatch):
    dist = _dist(tmp_path)
    monkeypatch.setattr(package_site, "MAX_FILES", 1)
    with pytest.raises(package_site.PackageError, match="file count"):
        package_site.build_manifest(dist)

    monkeypatch.setattr(package_site, "MAX_FILES", 10_000)
    monkeypatch.setattr(package_site, "MAX_BYTES", 4)
    with pytest.raises(package_site.PackageError, match="expanded output"):
        package_site.build_manifest(dist)

    monkeypatch.setattr(package_site, "MAX_BYTES", 100 * 1024 * 1024)
    with pytest.raises(package_site.PackageError, match="outside dist"):
        package_site.package(
            dist,
            dist / "site.zip",
            tmp_path / "manifest.json",
        )


def test_cli_prints_one_machine_readable_result(tmp_path, capsys):
    dist = _dist(tmp_path)
    archive = tmp_path / "site.zip"
    assert package_site.main([str(dist), str(archive)]) == 0
    captured = capsys.readouterr()
    result = json.loads(captured.out)
    assert result["ok"] is True
    assert result["file_count"] == 2
    assert captured.err == ""
