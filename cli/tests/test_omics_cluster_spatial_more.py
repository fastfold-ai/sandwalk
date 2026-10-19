"""Extra branches for methylation clustering, Moran's I, and MOFA integration."""

import builtins
import sys
import types

import numpy as np
import pandas as pd

from tools.omics import methylation_cluster, multiomics_integrate, spatial_autocorrelation


def _block_import(monkeypatch, module_name: str) -> None:
    """Make `import module_name` raise ImportError, including cached modules."""
    real_import = builtins.__import__

    def _import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == module_name or name.startswith(module_name + "."):
            raise ImportError(f"{module_name} is not installed")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", _import)
    for key in list(sys.modules):
        if key == module_name or key.startswith(module_name + "."):
            monkeypatch.delitem(sys.modules, key, raising=False)


class _Leiden:
    def __init__(self, labels):
        self._labels = list(labels)

    def value_counts(self):
        return pd.Series(self._labels).value_counts()

    def unique(self):
        seen = []
        for label in self._labels:
            if label not in seen:
                seen.append(label)
        return seen


class _Obs:
    def __init__(self, leiden):
        self._leiden = leiden

    def __getitem__(self, key):
        if key != "leiden":
            raise KeyError(key)
        return self._leiden


class _Var:
    def __init__(self, columns):
        self._columns = columns

    def __contains__(self, key):
        return key in self._columns

    def __getitem__(self, key):
        return self._columns[key]


class _MethylAdata:
    def __init__(self, *, n_obs=8, n_vars=6, highly_variable=True):
        self.n_obs = n_obs
        self.n_vars = n_vars
        rng = np.random.default_rng(0)
        self.X = rng.random((n_obs, n_vars))
        self.obs = _Obs(_Leiden(["0"] * (n_obs // 2) + ["1"] * (n_obs - n_obs // 2)))
        columns = {}
        if highly_variable:
            columns["highly_variable"] = np.ones(n_vars, dtype=bool)
        self.var = _Var(columns)
        self.uns = {
            "rank_features_groups": {
                "names": {
                    "0": ["c0", "c1", "c2", "c3", "c4", "c5"],
                    "1": ["d0", "d1", "d2", "d3", "d4", "d5"],
                }
            }
        }

    def __getitem__(self, _key):
        return self


class _Epi:
    def __init__(self, adata, *, filter_error=None, rank_error=None):
        self._adata = adata
        self._filter_error = filter_error
        self._rank_error = rank_error
        self.pp = self
        self.tl = self

    def read_h5ad(self, _path):
        return self._adata

    def filter_features(self, _adata, min_cells=1):
        if self._filter_error is not None:
            raise self._filter_error

    def select_var_feature(self, _adata, nb_features=10):
        return None

    def pca(self, _adata, n_comps=2):
        return None

    def neighbors(self, _adata, n_neighbors=15):
        return None

    def leiden(self, _adata, resolution=1.0):
        return None

    def rank_features(self, _adata, groupby="leiden"):
        if self._rank_error is not None:
            raise self._rank_error


class _Scanpy:
    def __init__(self, adata=None, *, read_error=None, hvg_error=None):
        self._adata = adata
        self._read_error = read_error
        self._hvg_error = hvg_error
        self.pp = self
        self.tl = self
        self.normalized = []

    def read_h5ad(self, _path):
        if self._read_error is not None:
            raise self._read_error
        return self._adata

    def highly_variable_genes(self, adata, n_top_genes=10, min_mean=0.0, max_mean=3, min_disp=0.5):
        if self._hvg_error is not None:
            raise self._hvg_error
        return None

    def pca(self, _adata, n_comps=2):
        return None

    def neighbors(self, _adata, n_neighbors=15, use_rep=None):
        return None

    def leiden(self, data, resolution=1.0, key_added=None):
        if key_added:
            data.obs = pd.DataFrame({key_added: ["0", "0", "1", "1"][: data.n_obs]})
        return None

    def normalize_total(self, adata, target_sum=1e4):
        self.normalized.append(adata)

    def log1p(self, _adata):
        return None


class _VarNames:
    def __init__(self, names):
        self._names = list(names)

    def __contains__(self, item):
        return item in self._names

    def __getitem__(self, key):
        mask = np.asarray(key, dtype=bool)
        return [name for name, keep in zip(self._names, mask) if keep]


class _SpatialAdata:
    def __init__(self, *, values, genes, highly, obsm, uns):
        self.X = np.full((4, len(genes)), values, dtype=float)
        self.n_obs = 4
        self.n_vars = len(genes)
        self.var_names = _VarNames(genes)
        self.var = pd.DataFrame({"highly_variable": highly})
        self.obsm = obsm
        self.uns = uns


def _install_squidpy(monkeypatch):
    module = types.ModuleType("squidpy")
    graph = types.SimpleNamespace(
        spatial_neighbors=lambda _adata: None,
        spatial_autocorr=lambda _adata, mode="moran", genes=None: None,
    )
    module.gr = graph
    monkeypatch.setitem(sys.modules, "squidpy", module)


def _write_beta_csv(path, n_sites=5, n_samples=4):
    frame = pd.DataFrame(
        np.arange(n_sites * n_samples, dtype=float).reshape(n_sites, n_samples),
        index=[f"cg{i}" for i in range(n_sites)],
        columns=[f"s{i}" for i in range(n_samples)],
    )
    frame.to_csv(path)
    return frame


def _install_fake_anndata(monkeypatch):
    module = types.ModuleType("anndata")

    class AnnData:
        def __init__(self, *, X, obs=None, var=None):
            self.X = np.asarray(X, dtype=float)
            self.obs = obs
            self.var = var
            self.n_obs = self.X.shape[0]
            self.n_vars = self.X.shape[1]
            self.uns = {}
            self.obsm = {}

    module.AnnData = AnnData
    monkeypatch.setitem(sys.modules, "anndata", module)


class _Modality:
    def __init__(self, n_obs, n_vars, fill):
        self.n_obs = n_obs
        self.n_vars = n_vars
        self.X = np.full((n_obs, n_vars), fill, dtype=float)


class _MuData:
    def __init__(self, modalities):
        self.mod = dict(modalities)
        self.n_obs = next(iter(self.mod.values())).n_obs
        self.obsm = {}
        self.obs = pd.DataFrame()


class _BadMuData:
    def __init__(self, _modalities):
        raise ValueError("obs mismatch")


class _QueueReader:
    def __init__(self, items):
        self._items = list(items)
        self.pp = _Scanpy()
        self.tl = self.pp

    def read_h5ad(self, _path):
        item = self._items.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def _install_mudata(monkeypatch, ctor):
    module = types.ModuleType("mudata")
    module.MuData = ctor
    monkeypatch.setitem(sys.modules, "mudata", module)


def _touch_h5ad(tmp_path, *names):
    paths = []
    for name in names:
        path = tmp_path / name
        path.write_bytes(b"h5ad")
        paths.append(path)
    return paths


class TestMethylationClusterMore:
    def test_h5ad_reader_error(self, monkeypatch, tmp_path):
        path = tmp_path / "beta.h5ad"
        path.write_bytes(b"not-h5ad")
        epi = _Epi(None)

        def _read(_path):
            raise RuntimeError("corrupt h5ad")

        epi.read_h5ad = _read
        monkeypatch.setattr("tools.omics._check_episcanpy", lambda: epi)
        monkeypatch.setattr("tools.omics._check_scanpy", lambda: None)

        result = methylation_cluster(str(path))

        assert "corrupt h5ad" in result["error"]
        assert "Load error" in result["summary"]

    def test_h5ad_scanpy_reader_error_when_epi_missing(self, monkeypatch, tmp_path):
        path = tmp_path / "beta.h5ad"
        path.write_bytes(b"not-h5ad")
        scanpy = _Scanpy(read_error=RuntimeError("scanpy cannot read"))
        monkeypatch.setattr("tools.omics._check_episcanpy", lambda: None)
        monkeypatch.setattr("tools.omics._check_scanpy", lambda: scanpy)

        result = methylation_cluster(str(path))

        assert "scanpy cannot read" in result["error"]

    def test_empty_table_returns_load_error(self, monkeypatch, tmp_path):
        path = tmp_path / "empty.csv"
        path.write_text("", encoding="utf-8")
        monkeypatch.setattr("tools.omics._check_episcanpy", lambda: None)
        monkeypatch.setattr("tools.omics._check_scanpy", lambda: None)

        result = methylation_cluster(str(path))

        assert "error" in result
        assert "Failed to read" in result["error"]
        assert result["summary"].startswith("Could not load:")

    def test_anndata_missing_while_scanpy_present(self, monkeypatch, tmp_path):
        path = tmp_path / "beta.csv"
        _write_beta_csv(path)
        _block_import(monkeypatch, "anndata")
        monkeypatch.setattr("tools.omics._check_episcanpy", lambda: None)
        monkeypatch.setattr("tools.omics._check_scanpy", lambda: object())

        result = methylation_cluster(str(path))

        assert "anndata required" in result["error"]
        assert result["summary"] == "Install anndata"

    def test_tabular_anndata_falls_through_to_sklearn(self, monkeypatch, tmp_path):
        path = tmp_path / "beta.csv"
        _write_beta_csv(path, n_sites=6, n_samples=8)
        _install_fake_anndata(monkeypatch)
        monkeypatch.setattr("tools.omics._check_episcanpy", lambda: None)
        monkeypatch.setattr("tools.omics._check_scanpy", lambda: None)

        result = methylation_cluster(str(path))

        assert "sklearn" in result["method"]
        assert result["n_samples"] == 8
        assert result["n_features_input"] == 6
        assert result["n_clusters"] >= 2
        assert all(isinstance(key, str) for key in result["cluster_sizes"])

    def test_episcanpy_success_with_markers(self, monkeypatch, tmp_path):
        path = tmp_path / "beta.h5ad"
        path.write_bytes(b"h5ad")
        adata = _MethylAdata()
        epi = _Epi(adata)
        monkeypatch.setattr("tools.omics._check_episcanpy", lambda: epi)
        monkeypatch.setattr("tools.omics._check_scanpy", lambda: None)

        result = methylation_cluster(str(path), n_top_features=10, resolution=0.6)

        assert result["method"] == "episcanpy"
        assert result["n_samples"] == 8
        assert result["n_features_input"] == 6
        assert result["n_clusters"] == 2
        assert result["cluster_sizes"]["0"] == 4
        assert result["cluster_markers"]["0"] == ["c0", "c1", "c2", "c3", "c4"]
        assert result["cluster_markers"]["1"] == ["d0", "d1", "d2", "d3", "d4"]
        assert "episcanpy" in result["summary"]

    def test_episcanpy_without_variable_features_skips_failed_markers(self, monkeypatch, tmp_path):
        path = tmp_path / "beta.h5ad"
        path.write_bytes(b"h5ad")
        adata = _MethylAdata(highly_variable=False)
        epi = _Epi(adata, rank_error=RuntimeError("rank failed"))
        monkeypatch.setattr("tools.omics._check_episcanpy", lambda: epi)
        monkeypatch.setattr("tools.omics._check_scanpy", lambda: None)

        result = methylation_cluster(str(path))

        assert result["method"] == "episcanpy"
        assert result["n_features_used"] == adata.n_vars
        assert "cluster_markers" not in result

    def test_episcanpy_failure_uses_scanpy(self, monkeypatch, tmp_path):
        path = tmp_path / "beta.h5ad"
        path.write_bytes(b"h5ad")
        adata = _MethylAdata()
        epi = _Epi(adata, filter_error=RuntimeError("epi pipeline down"))
        scanpy = _Scanpy(adata)
        monkeypatch.setattr("tools.omics._check_episcanpy", lambda: epi)
        monkeypatch.setattr("tools.omics._check_scanpy", lambda: scanpy)

        result = methylation_cluster(str(path))

        assert result["method"].startswith("scanpy")
        assert result["n_clusters"] == 2
        assert result["n_features_used"] == adata.n_vars
        assert "scanpy fallback" in result["summary"]

    def test_scanpy_failure_uses_sklearn(self, monkeypatch, tmp_path):
        path = tmp_path / "beta.h5ad"
        path.write_bytes(b"h5ad")
        adata = _MethylAdata(n_obs=8, n_vars=5)
        scanpy = _Scanpy(adata, hvg_error=RuntimeError("hvg failed"))
        monkeypatch.setattr("tools.omics._check_episcanpy", lambda: None)
        monkeypatch.setattr("tools.omics._check_scanpy", lambda: scanpy)

        result = methylation_cluster(str(path))

        assert "sklearn" in result["method"]
        assert result["n_samples"] == 8
        assert result["n_features_input"] == 5
        assert result["n_clusters"] >= 2


class TestSpatialAutocorrelationMore:
    def test_read_error(self, monkeypatch, tmp_path):
        path = tmp_path / "spatial.h5ad"
        path.write_bytes(b"h5ad")
        scanpy = _Scanpy(read_error=RuntimeError("truncated file"))
        monkeypatch.setattr("tools.omics._check_scanpy", lambda: scanpy)

        result = spatial_autocorrelation(str(path))

        assert "truncated file" in result["error"]
        assert "Read error" in result["summary"]

    def test_missing_spatial_coordinates(self, monkeypatch, tmp_path):
        path = tmp_path / "spatial.h5ad"
        path.write_bytes(b"h5ad")
        adata = _SpatialAdata(
            values=1.0,
            genes=["G1"],
            highly=[True],
            obsm=None,
            uns={},
        )
        monkeypatch.setattr("tools.omics._check_scanpy", lambda: _Scanpy(adata))

        result = spatial_autocorrelation(str(path))

        assert "No spatial coordinates" in result["error"]
        assert "Not spatial data" in result["summary"]

    def test_squidpy_missing(self, monkeypatch, tmp_path):
        path = tmp_path / "spatial.h5ad"
        path.write_bytes(b"h5ad")
        adata = _SpatialAdata(
            values=1.0,
            genes=["G1"],
            highly=[True],
            obsm={"spatial": np.zeros((4, 2))},
            uns={},
        )
        _block_import(monkeypatch, "squidpy")
        monkeypatch.setattr("tools.omics._check_scanpy", lambda: _Scanpy(adata))

        result = spatial_autocorrelation(str(path))

        assert "squidpy required" in result["error"]
        assert "Install squidpy" in result["summary"]

    def test_default_genes_normalize_raw_counts(self, monkeypatch, tmp_path):
        path = tmp_path / "spatial.h5ad"
        path.write_bytes(b"h5ad")
        moran = pd.DataFrame(
            {"I": [0.9, 0.2, 0.8], "pval_norm": [0.01, 0.4, 0.04]},
            index=["G1", "G2", "G3"],
        )
        adata = _SpatialAdata(
            values=100.0,
            genes=["G1", "G2", "G3"],
            highly=[True, True, False],
            obsm={"spatial": np.zeros((4, 2))},
            uns={"moranI": moran},
        )
        scanpy = _Scanpy(adata)
        _install_squidpy(monkeypatch)
        monkeypatch.setattr("tools.omics._check_scanpy", lambda: scanpy)

        result = spatial_autocorrelation(str(path), genes="  ,  ", n_genes=2)

        assert scanpy.normalized == [adata]
        assert result["n_genes_tested"] == 2
        assert result["n_spatially_patterned"] == 2
        assert "G1" in result["top_spatial_genes"]
        assert "G1 (I=0.900)" in result["summary"]

    def test_specified_genes_skip_normalization(self, monkeypatch, tmp_path):
        path = tmp_path / "spatial.h5ad"
        path.write_bytes(b"h5ad")
        moran = pd.DataFrame(
            {"I": [0.4, 0.1], "pval_norm": [0.2, 0.8]},
            index=["G1", "G3"],
        )
        adata = _SpatialAdata(
            values=3.0,
            genes=["G1", "G2", "G3"],
            highly=[True, True, True],
            obsm={"spatial": np.zeros((4, 2))},
            uns={"moranI": moran},
        )
        scanpy = _Scanpy(adata)
        _install_squidpy(monkeypatch)
        monkeypatch.setattr("tools.omics._check_scanpy", lambda: scanpy)

        result = spatial_autocorrelation(str(path), genes="G1, G3")

        assert scanpy.normalized == []
        assert result["n_genes_tested"] == 2
        assert result["n_spatially_patterned"] == 0
        assert "G1 (I=0.400)" in result["summary"]

    def test_no_matching_genes(self, monkeypatch, tmp_path):
        path = tmp_path / "spatial.h5ad"
        path.write_bytes(b"h5ad")
        adata = _SpatialAdata(
            values=1.0,
            genes=["G1", "G2"],
            highly=[False, False],
            obsm={"spatial": np.zeros((4, 2))},
            uns={},
        )
        _install_squidpy(monkeypatch)
        monkeypatch.setattr("tools.omics._check_scanpy", lambda: _Scanpy(adata))

        result = spatial_autocorrelation(str(path), genes="ZZZ, ")

        assert "None of the specified genes" in result["error"]
        assert "No matching genes" in result["summary"]

    def test_moran_result_missing(self, monkeypatch, tmp_path):
        path = tmp_path / "spatial.h5ad"
        path.write_bytes(b"h5ad")
        adata = _SpatialAdata(
            values=1.0,
            genes=["G1"],
            highly=[True],
            obsm={"spatial": np.zeros((4, 2))},
            uns={},
        )
        _install_squidpy(monkeypatch)
        monkeypatch.setattr("tools.omics._check_scanpy", lambda: _Scanpy(adata))

        result = spatial_autocorrelation(str(path), genes="G1")

        assert result["error"] == "Moran's I computation failed"
        assert "failed" in result["summary"]


class TestMultiomicsIntegrateMore:
    def _patch_libs(self, monkeypatch, reader, mofa):
        muon = types.SimpleNamespace(tl=types.SimpleNamespace(mofa=mofa))
        monkeypatch.setattr("tools.omics._check_muon", lambda: muon)
        monkeypatch.setattr("tools.omics._check_scanpy", lambda: reader)
        return reader

    def test_second_modality_load_error(self, monkeypatch, tmp_path):
        rna, atac = _touch_h5ad(tmp_path, "rna.h5ad", "atac.h5ad")
        reader = _QueueReader([_Modality(4, 3, 10.0), RuntimeError("bad header")])
        self._patch_libs(monkeypatch, reader, lambda *_args, **_kwargs: None)

        result = multiomics_integrate(
            paths=f"{rna},{atac}",
            modality_names="rna,atac",
        )

        assert "bad header" in result["error"]
        assert "Load error" in result["summary"]

    def test_mudata_import_error(self, monkeypatch, tmp_path):
        rna, atac = _touch_h5ad(tmp_path, "rna.h5ad", "atac.h5ad")
        reader = _QueueReader([_Modality(4, 2, 1.0), _Modality(4, 2, 1.0)])
        self._patch_libs(monkeypatch, reader, lambda *_args, **_kwargs: None)
        _block_import(monkeypatch, "mudata")

        result = multiomics_integrate(paths=f"{rna},{atac}", modality_names="rna,atac")

        assert "mudata required" in result["error"]
        assert "Install mudata" in result["summary"]

    def test_mudata_creation_error(self, monkeypatch, tmp_path):
        rna, atac = _touch_h5ad(tmp_path, "rna.h5ad", "atac.h5ad")
        reader = _QueueReader([_Modality(4, 2, 1.0), _Modality(3, 2, 1.0)])
        self._patch_libs(monkeypatch, reader, lambda *_args, **_kwargs: None)
        _install_mudata(monkeypatch, _BadMuData)

        result = multiomics_integrate(paths=f"{rna},{atac}", modality_names="rna,atac")

        assert "obs mismatch" in result["error"]
        assert "Integration setup error" in result["summary"]

    def test_mofa_failure_reports_shapes(self, monkeypatch, tmp_path):
        rna, atac = _touch_h5ad(tmp_path, "rna.h5ad", "atac.h5ad")
        raw = _Modality(4, 5, 80.0)
        scaled = _Modality(4, 2, 1.0)
        reader = _QueueReader([raw, scaled])
        self._patch_libs(monkeypatch, reader, self._mofa_boom)
        _install_mudata(monkeypatch, _MuData)

        result = multiomics_integrate(paths=f"{rna},{atac}", modality_names="rna, protein")

        assert "MOFA+ failed" in result["error"]
        assert result["n_shared_cells"] == 4
        assert result["modality_shapes"]["rna"] == (4, 5)
        assert result["modality_shapes"]["protein"] == (4, 2)
        assert reader.pp.normalized == [raw]

    @staticmethod
    def _mofa_boom(_mdata, n_factors=10, quiet=True):
        raise RuntimeError("solver blew up")

    def test_mofa_without_embedding(self, monkeypatch, tmp_path):
        rna, atac = _touch_h5ad(tmp_path, "rna.h5ad", "atac.h5ad")
        reader = _QueueReader([_Modality(4, 2, 1.0), _Modality(4, 2, 1.0)])
        self._patch_libs(monkeypatch, reader, lambda *_args, **_kwargs: None)
        _install_mudata(monkeypatch, _MuData)

        result = multiomics_integrate(paths=f"{rna},{atac}", modality_names="rna,atac")

        assert result["error"] == "MOFA+ did not produce embeddings"
        assert "no factors" in result["summary"]

    def test_success_auto_names_and_joint_clusters(self, monkeypatch, tmp_path):
        rna, atac = _touch_h5ad(tmp_path, "rna.h5ad", "atac.h5ad")
        raw = _Modality(4, 6, 100.0)
        scaled = _Modality(4, 3, 2.0)
        reader = _QueueReader([raw, scaled])

        def _mofa(mdata, n_factors=10, quiet=True):
            assert quiet is True
            assert n_factors == 3
            mdata.obsm["X_mofa"] = np.zeros((mdata.n_obs, n_factors))

        self._patch_libs(monkeypatch, reader, _mofa)
        _install_mudata(monkeypatch, _MuData)

        result = multiomics_integrate(paths=f"{rna}, {atac}", modality_names="", n_factors=3)

        assert result["modalities"] == ["modality_0", "modality_1"]
        assert result["n_factors"] == 3
        assert result["n_shared_cells"] == 4
        assert result["n_joint_clusters"] == 2
        assert result["joint_cluster_sizes"]["0"] == 2
        assert result["modality_shapes"]["modality_0"] == (4, 6)
        assert reader.pp.normalized == [raw]
        assert "MOFA+" in result["summary"]
        assert "2 joint clusters" in result["summary"]
