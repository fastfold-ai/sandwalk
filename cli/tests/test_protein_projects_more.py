"""Extra branches for domain annotation, cell-type labels, and project routes."""

from __future__ import annotations

import asyncio
import sys
import types
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
from fastapi import FastAPI, HTTPException

from agent_server.models import (
    CreateProjectRequest,
    RenameProjectFolderFileRequest,
    UpdateProjectRequest,
    UseProjectFolderInChatRequest,
)
from agent_server.routes import projects as project_routes
from tools.protein_domains import domain_annotate
from tools.singlecell import cell_type_annotate


class _Resp:
    def __init__(self, status_code=200, payload=None, broken=False):
        self.status_code = status_code
        self.payload = {} if payload is None else payload
        self.broken = broken

    def json(self):
        if self.broken:
            raise ValueError("not json")
        return self.payload


def _call(monkeypatch, script, **kwargs):
    steps = iter(script)

    def request(method, url, **request_kwargs):
        try:
            return next(steps)
        except StopIteration as exc:
            raise AssertionError(f"unexpected HTTP {method} {url}") from exc

    monkeypatch.setattr("tools.protein_domains.request", request)
    return domain_annotate(**kwargs)


def _meta(accession, name, etype, description=None):
    metadata = {
        "accession": accession,
        "name": name,
        "type": etype,
        "source_database": "interpro",
    }
    if description is not None:
        metadata["description"] = description
    return {"metadata": metadata}


def _protein_entry(accession, name, etype, locations=None, description=None):
    entry = _meta(accession, name, etype, description)
    proteins = []
    if locations is not None:
        proteins.append(
            {
                "entry_protein_locations": [
                    {"fragments": [{"start": start, "end": end} for start, end in locations]}
                ]
            }
        )
    entry["proteins"] = proteins
    return entry


def test_uniprot_failures_and_blank_keyword(monkeypatch):
    blank = _call(
        monkeypatch,
        [(None, "timeout"), (_Resp(status_code=503), None)],
        gene="   ",
    )
    assert "resolve" in blank["error"].lower()
    assert "mode" not in blank

    unresolved = _call(
        monkeypatch,
        [
            (_Resp(broken=True), None),
            (_Resp(payload={"results": []}), None),
            (None, "down"),
            (_Resp(broken=True), None),
        ],
        gene="NOGENE1",
    )
    assert "resolve" in unresolved["error"].lower()
    assert unresolved["resolution_attempts"]


def test_blank_accession_then_sites_and_single_domain(monkeypatch):
    payload = {
        "results": [
            _protein_entry("IPR000001", "Kinase", "domain"),
            _protein_entry("IPR000002", "Kinase family", "family", description=[]),
            _protein_entry("IPR000003", "Active", "active_site", locations=[(1, 4)]),
            _protein_entry("IPR000004", "Bind", "binding_site", locations=[(5, 8)]),
            _protein_entry("IPR000005", "Conserved", "conserved_site"),
            _protein_entry("IPR000006", "PTM", "ptm"),
            _protein_entry("IPR000007", "Super", "homologous_superfamily"),
            _protein_entry("IPR000008", "Other", "repeat"),
        ]
    }
    result = _call(
        monkeypatch,
        [
            (_Resp(payload={"results": [{"primaryAccession": ""}]}), None),
            (_Resp(payload={"results": [{"primaryAccession": "P99999"}]}), None),
            (_Resp(payload=payload), None),
        ],
        gene="TP53X",
    )
    assert result["uniprot_id"] == "P99999"
    assert result["n_domains"] == 1
    assert result["n_families"] == 1
    assert result["n_sites"] == 4
    assert len(result["homologous_superfamilies"]) == 1
    assert "1 domain" in result["summary"]
    assert "(" not in result["summary"]


def test_keyword_search_mixed_types(monkeypatch):
    result = _call(
        monkeypatch,
        [
            (_Resp(status_code=500), None),
            (_Resp(payload={"results": [{"primaryAccession": ""}]}), None),
            (_Resp(payload={"results": []}), None),
            (
                _Resp(
                    payload={
                        "results": [
                            _meta("IPR100001", "CAP", "domain", [{"text": "CAP domain"}]),
                            _meta("IPR100002", "CAP family", "family", "not-a-list"),
                            _meta("IPR100003", "Repeat", "repeat"),
                            {"metadata": None},
                        ]
                    }
                ),
                None,
            ),
        ],
        gene="CAP superfamily term",
    )
    assert result["mode"] == "interpro_keyword_search"
    assert result["n_domains"] == 1
    assert result["n_families"] == 1
    assert result["domains"][0]["description"] == "CAP domain"
    assert result["families"][0]["description"] == ""


def test_interpro_accession_fallbacks(monkeypatch):
    keyword = _call(
        monkeypatch,
        [
            (None, "nope"),
            (_Resp(payload={"results": []}), None),
            (_Resp(payload={"results": [_meta("IPR014044", "CAP", "domain")]}), None),
        ],
        uniprot_id="  ipr014044 ",
    )
    assert keyword["mode"] == "interpro_keyword_search"
    assert keyword["n_domains"] == 1
    assert keyword["uniprot_id"] is None

    invalid = _call(monkeypatch, [(_Resp(broken=True), None)], uniprot_id="IPR000444")
    assert "Invalid InterPro" in invalid["error"]

    empty = _call(
        monkeypatch,
        [(_Resp(payload={"results": []}), None)],
        uniprot_id="IPR000111",
    )
    assert "No InterPro entry" in empty["error"]

    looked_up = _call(
        monkeypatch,
        [
            (
                _Resp(
                    payload={
                        "results": [
                            _meta("IPR014046", "CAP family", "family", "plain"),
                            _meta("IPR014047", "Repeat", "repeat"),
                            _meta("IPR014045", "CAP", "domain", [{"text": "domain text"}]),
                        ]
                    }
                ),
                None,
            )
        ],
        uniprot_id="IPR014045",
    )
    assert looked_up["mode"] == "interpro_accession_lookup"
    assert looked_up["n_domains"] == 1
    assert looked_up["n_families"] == 1
    assert looked_up["families"][0]["description"] == ""

    failed = _call(
        monkeypatch,
        [(_Resp(status_code=404), None), (None, "kw"), (_Resp(status_code=500), None)],
        uniprot_id="IPR000222",
    )
    assert "IPR000222" in failed["error"]


def test_interpro_protein_query_errors(monkeypatch):
    recovered = _call(
        monkeypatch,
        [
            (_Resp(payload={"results": [{"primaryAccession": "P11111"}]}), None),
            (None, "interpro down"),
            (_Resp(payload={"results": [_meta("IPR200001", "WD40", "domain")]}), None),
        ],
        gene="BRCA9",
    )
    assert recovered["mode"] == "interpro_keyword_search"
    assert recovered["n_domains"] == 1

    http_fail = _call(
        monkeypatch,
        [
            (_Resp(payload={"results": [{"primaryAccession": "P22222"}]}), None),
            (_Resp(status_code=500), None),
            (None, "kw"),
            (_Resp(status_code=404), None),
        ],
        gene="BRCA8",
    )
    assert "HTTP 500" in http_fail["error"]

    api_error = _call(monkeypatch, [(None, "down")], uniprot_id="P33333")
    assert "InterPro API error" in api_error["error"]

    status_only = _call(monkeypatch, [(_Resp(status_code=418), None)], uniprot_id="P44444")
    assert "HTTP 418" in status_only["error"]

    broken = _call(monkeypatch, [(_Resp(broken=True), None)], uniprot_id="P55555")
    assert "Invalid InterPro response" in broken["error"]

    keyword_miss = _call(
        monkeypatch,
        [
            (_Resp(payload={"results": [{"primaryAccession": "P66666"}]}), None),
            (None, "interpro down"),
            (None, "kw"),
            (_Resp(status_code=404), None),
        ],
        gene="BRCA7",
    )
    assert "InterPro API error" in keyword_miss["error"]

    status_recovered = _call(
        monkeypatch,
        [
            (_Resp(payload={"results": [{"primaryAccession": "P77777"}]}), None),
            (_Resp(status_code=500), None),
            (_Resp(payload={"results": [_meta("IPR300001", "SH2", "domain")]}), None),
        ],
        gene="BRCA6",
    )
    assert status_recovered["mode"] == "interpro_keyword_search"
    assert status_recovered["uniprot_id"] is None


class _Sparse:
    def __init__(self, values):
        self.values = np.asarray(values)

    def __getitem__(self, key):
        return _Sparse(self.values[np.asarray(key)])

    def toarray(self):
        return self.values


def _adata(matrix, genes, clusters, cluster_key="leiden"):
    values = matrix if isinstance(matrix, _Sparse) else np.asarray(matrix, dtype=float)
    shape = values.values.shape if isinstance(values, _Sparse) else values.shape
    return SimpleNamespace(
        shape=shape,
        X=values,
        var_names=list(genes),
        obs=pd.DataFrame({cluster_key: list(clusters)}),
    )


def _use_scanpy(monkeypatch, adata=None, error=None):
    def read_h5ad(path):
        if error is not None:
            raise error
        return adata

    monkeypatch.setattr(
        "tools.singlecell_annotate._singlecell._check_scanpy",
        lambda: SimpleNamespace(read_h5ad=read_h5ad),
    )


def test_annotation_load_paths(tmp_path, monkeypatch):
    _use_scanpy(monkeypatch, adata=_adata([[0.0]], ["ZZZ"], ["A"], cluster_key="batch"))
    loaded = cell_type_annotate(str(tmp_path / "cells.h5ad"), reference="tissue")
    assert "cluster" in loaded["error"].lower()

    unsupported = cell_type_annotate(str(tmp_path / "matrix.mtx"))
    assert "Unsupported file format" in unsupported["error"]

    _use_scanpy(monkeypatch, error=OSError("unreadable"))
    failed = cell_type_annotate(str(tmp_path / "broken.h5ad"))
    assert "unreadable" in failed["error"]


def test_marker_scores_sparse_unknown_and_zero(monkeypatch):
    _use_scanpy(
        monkeypatch,
        adata=_adata(_Sparse([[5.0], [4.0]]), ["CD3D"], ["0", "0"]),
    )
    scored = cell_type_annotate("panel.h5ad", reference="custom")
    assert scored["annotations"]["0"]["cell_type"] == "T cells"
    assert scored["annotations"]["0"]["confidence"] > 0
    assert scored["reference"] == "custom"

    _use_scanpy(monkeypatch, adata=_adata([[0.0]], ["CD3D"], ["NK"]))
    quiet = cell_type_annotate("zero.h5ad", reference="pbmc")
    assert quiet["annotations"]["NK"]["cell_type"] == "T cells"
    assert quiet["annotations"]["NK"]["confidence"] == 0.0
    assert quiet["annotations"]["NK"]["marker_score"] == 0.0

    _use_scanpy(monkeypatch, adata=_adata([[1.0, 2.0]], ["NOPE", "ALSO"], ["c"]))
    unknown = cell_type_annotate("unknown.h5ad", reference="tissue")
    assert unknown["annotations"]["c"]["cell_type"] == "Unknown"
    assert unknown["annotations"]["c"]["all_scores"] == {}
    assert unknown["cell_type_distribution"]["Unknown"] == "100%"


def _install_celltypist(monkeypatch, annotate, download=None):
    models = types.ModuleType("celltypist.models")

    class Model:
        @staticmethod
        def load(model="Immune_All_Low.pkl"):
            return model

    models.Model = Model
    models.download_models = download or (lambda force_update=False: None)
    module = types.ModuleType("celltypist")
    module.models = models
    module.annotate = annotate
    monkeypatch.setitem(sys.modules, "celltypist", module)
    monkeypatch.setitem(sys.modules, "celltypist.models", models)


def test_celltypist_votes_and_failure(monkeypatch):
    adata = _adata(
        [[0.0], [0.0], [0.0], [0.0]],
        ["CD3D"],
        ["0", "0", "0", "1"],
    )
    result_obs = pd.DataFrame({"majority_voting": ["T cell", "NK", "T cell", None]})

    def annotate(adata_in, model=None, majority_voting=True):
        assert model == "Immune_All_Low.pkl"
        assert majority_voting is True
        return SimpleNamespace(to_adata=lambda: SimpleNamespace(obs=result_obs))

    _install_celltypist(monkeypatch, annotate)
    _use_scanpy(monkeypatch, adata=adata)
    labeled = cell_type_annotate("typed.h5ad", method="celltypist")
    assert labeled["method"] == "celltypist"
    assert labeled["annotations"]["0"]["cell_type"] == "T cell"
    assert labeled["annotations"]["0"]["confidence"] == 0.667
    assert labeled["annotations"]["1"]["cell_type"] == "Unknown"
    assert labeled["annotations"]["1"]["confidence"] == 0.0
    assert labeled["n_clusters"] == 2

    def explode(force_update=False):
        raise RuntimeError("catalog down")

    _install_celltypist(monkeypatch, annotate, download=explode)
    failed = cell_type_annotate("typed.h5ad", method="celltypist")
    assert "CellTypist annotation failed" in failed["error"]
    assert "catalog down" in failed["error"]


class _Store:
    def __init__(self):
        self.project = None
        self.updated = None
        self.raise_on_create = False
        self.raise_on_update = False
        self.deleted = False

    def list_projects(self):
        return []

    def create_project(self, **kwargs):
        if self.raise_on_create:
            raise ValueError("name taken")
        return kwargs

    def get_project(self, project_id):
        return self.project

    def update_project(self, project_id, **kwargs):
        if self.raise_on_update:
            raise ValueError("bad update")
        return self.updated

    def delete_project(self, project_id):
        return self.deleted


def _routes(monkeypatch, store):
    async def inline(func, /, *args, **kwargs):
        return func(*args, **kwargs)

    monkeypatch.setattr(project_routes.asyncio, "to_thread", inline)
    app = FastAPI()
    project_routes.register_project_routes(app, SimpleNamespace(store=store, service=object()))
    return {
        route.endpoint.__name__: route.endpoint
        for route in app.routes
        if getattr(route, "endpoint", None) is not None
    }


def _status(coro):
    with pytest.raises(HTTPException) as caught:
        asyncio.run(coro)
    return caught.value.status_code, caught.value.detail


def test_project_route_error_branches(tmp_path, monkeypatch):
    store = _Store()
    routes = _routes(monkeypatch, store)
    folder = tmp_path / "proj"
    folder.mkdir()
    (folder / "a.txt").write_text("alpha")
    (folder / "b.txt").write_text("beta")
    not_dir = tmp_path / "notes.txt"
    not_dir.write_text("nope")

    store.raise_on_create = True
    status, detail = _status(routes["create_project"](CreateProjectRequest(name="X")))
    assert status == 400
    assert detail == "name taken"

    status, detail = _status(routes["get_project"]("missing"))
    assert status == 404
    assert detail == "Project not found."

    status, _detail = _status(routes["get_project_folder_files"]("missing"))
    assert status == 404
    store.project = SimpleNamespace(folder_path=None)
    status, detail = _status(routes["get_project_folder_files"]("p1"))
    assert status == 404
    assert "no linked folder" in detail
    store.project = SimpleNamespace(folder_path=str(not_dir))
    status, detail = _status(routes["get_project_folder_files"]("p1"))
    assert status == 400
    assert "not a directory" in detail

    store.project = None
    status, _detail = _status(routes["get_project_folder_file_content"]("missing", "a.txt"))
    assert status == 404
    store.project = SimpleNamespace(folder_path="")
    status, detail = _status(routes["get_project_folder_file_content"]("p1", "a.txt"))
    assert status == 404
    assert "no linked folder" in detail
    store.project = SimpleNamespace(folder_path=str(folder))
    status, detail = _status(routes["get_project_folder_file_content"]("p1", "gone.txt"))
    assert status == 404
    assert detail == "File not found."
    status, detail = _status(routes["get_project_folder_file_content"]("p1", "../secret"))
    assert status == 400
    assert "Invalid" in detail

    store.project = None
    rename = RenameProjectFolderFileRequest(path="a.txt", name="c.txt")
    status, _detail = _status(routes["rename_project_folder_file_route"]("missing", rename))
    assert status == 404
    store.project = SimpleNamespace(folder_path=None)
    status, detail = _status(routes["rename_project_folder_file_route"]("p1", rename))
    assert status == 404
    assert "no linked folder" in detail
    store.project = SimpleNamespace(folder_path=str(folder))
    missing_rename = RenameProjectFolderFileRequest(path="gone.txt", name="c.txt")
    status, detail = _status(routes["rename_project_folder_file_route"]("p1", missing_rename))
    assert status == 404
    assert detail == "File not found."
    clash = RenameProjectFolderFileRequest(path="a.txt", name="b.txt")
    status, detail = _status(routes["rename_project_folder_file_route"]("p1", clash))
    assert status == 400
    assert "already exists" in detail

    store.project = None
    status, _detail = _status(routes["delete_project_folder_file_route"]("missing", "a.txt"))
    assert status == 404
    store.project = SimpleNamespace(folder_path=None)
    status, detail = _status(routes["delete_project_folder_file_route"]("p1", "a.txt"))
    assert status == 404
    assert "no linked folder" in detail
    store.project = SimpleNamespace(folder_path=str(folder))
    status, detail = _status(routes["delete_project_folder_file_route"]("p1", "gone.txt"))
    assert status == 404
    assert detail == "File not found."
    status, detail = _status(routes["delete_project_folder_file_route"]("p1", "../secret"))
    assert status == 400
    assert "Invalid" in detail

    chat = UseProjectFolderInChatRequest(paths=["gone.txt"])
    store.project = None
    status, _detail = _status(routes["use_project_folder_in_chat_route"]("missing", chat))
    assert status == 404
    store.project = SimpleNamespace(folder_path=None)
    status, detail = _status(routes["use_project_folder_in_chat_route"]("p1", chat))
    assert status == 404
    assert "no linked folder" in detail
    store.project = SimpleNamespace(folder_path=str(folder))
    status, detail = _status(routes["use_project_folder_in_chat_route"]("p1", chat))
    assert status == 404
    assert detail == "File not found."
    escaped = UseProjectFolderInChatRequest(paths=["../secret"])
    status, detail = _status(routes["use_project_folder_in_chat_route"]("p1", escaped))
    assert status == 400
    assert "Invalid" in detail

    store.raise_on_update = True
    status, detail = _status(routes["update_project"]("p1", UpdateProjectRequest(name="Y")))
    assert status == 400
    assert detail == "bad update"
    store.raise_on_update = False
    store.updated = None
    status, detail = _status(routes["update_project"]("p1", UpdateProjectRequest(clear_description=True)))
    assert status == 404
    assert detail == "Project not found."

    store.deleted = False
    status, detail = _status(routes["delete_project"]("missing"))
    assert status == 404
    assert detail == "Project not found."
