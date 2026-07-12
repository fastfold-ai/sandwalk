"""Additional bulk tests for tools.omics helpers and entry points."""

import gzip
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from tools.omics import (
    KEGG_ORA_SYSTEM_PROMPT,
    _check_episcanpy,
    _check_muon,
    _check_pydeseq2,
    _inspect_h5ad,
    _inspect_matrix_gz,
    _inspect_tabular,
    dataset_info,
    deseq2,
    kegg_ora,
)


def _run_kegg_ora(gene_ids, all_kegg_genes, path2genes, path_names, min_size=5, max_size=500):
    """Inline copy of the KEGG ORA helper from the omics prompt template."""
    from scipy.stats import fisher_exact
    from statsmodels.stats.multitest import multipletests

    deg_kegg = set(gene_ids) & all_kegg_genes
    n = len(deg_kegg)
    n_background = len(all_kegg_genes)
    if n == 0:
        return pd.DataFrame()
    results = []
    for pid, pgenes in path2genes.items():
        pathway_size = len(pgenes)
        if pathway_size < min_size or pathway_size > max_size:
            continue
        overlap = len(deg_kegg & pgenes)
        if overlap == 0:
            continue
        _, pval = fisher_exact(
            [[overlap, n - overlap], [pathway_size - overlap, n_background - pathway_size - n + overlap]],
            alternative="greater",
        )
        results.append(
            {
                "pathway": pid,
                "name": path_names.get(pid, ""),
                "overlap": overlap,
                "pathway_size": pathway_size,
                "pvalue": pval,
            }
        )
    if not results:
        return pd.DataFrame()
    res_df = pd.DataFrame(results)
    _, res_df["padj"], _, _ = multipletests(res_df["pvalue"], method="fdr_bh")
    return res_df


class TestOptionalDepChecks:
    def test_check_pydeseq2_import_error(self):
        with patch.dict("sys.modules", {"pydeseq2": None, "pydeseq2.dds": None, "pydeseq2.ds": None}):
            with patch(
                "builtins.__import__",
                side_effect=lambda name, *args, **kwargs: (_ for _ in ()).throw(ImportError(name)),
            ):
                assert _check_pydeseq2() is False

    def test_check_muon_import_error(self):
        with patch.dict("sys.modules", {"muon": None, "mudata": None}):
            with patch(
                "builtins.__import__",
                side_effect=lambda name, *args, **kwargs: (_ for _ in ()).throw(ImportError(name)),
            ):
                assert _check_muon() is None

    def test_check_episcanpy_import_error(self):
        with patch.dict("sys.modules", {"episcanpy": None, "episcanpy.api": None}):
            with patch(
                "builtins.__import__",
                side_effect=lambda name, *args, **kwargs: (_ for _ in ()).throw(ImportError(name)),
            ):
                assert _check_episcanpy() is None


class TestDatasetInfo:
    def test_missing_path(self):
        result = dataset_info(path="")
        assert "No path provided" in result["summary"]

    def test_file_not_found(self, tmp_path):
        result = dataset_info(path=str(tmp_path / "missing.csv"))
        assert "File not found" in result["summary"]

    def test_csv_inspection(self, tmp_path):
        csv_path = tmp_path / "counts.csv"
        pd.DataFrame({"s1": [1, 2], "s2": [3, 4]}, index=["GENE1", "GENE2"]).to_csv(csv_path)
        result = dataset_info(path=str(csv_path))
        assert result["file_type"] == "csv"
        assert "GENE1" in result["summary"] or "2 rows" in result["summary"]

    def test_tsv_inspection(self, tmp_path):
        tsv_path = tmp_path / "data.tsv"
        pd.DataFrame({"a": [1], "b": [2]}, index=["row1"]).to_csv(tsv_path, sep="\t")
        result = dataset_info(path=str(tsv_path))
        assert result["file_type"] == "tsv"

    def test_unknown_suffix(self, tmp_path):
        path = tmp_path / "data.xyz"
        path.write_text("binary-ish")
        result = dataset_info(path=str(path))
        assert "not directly inspectable" in result["summary"]

    def test_inspection_exception(self, tmp_path, monkeypatch):
        csv_path = tmp_path / "bad.csv"
        csv_path.write_text("not,a,valid\n1\n")
        monkeypatch.setattr("tools.omics._inspect_tabular", lambda *_a, **_k: (_ for _ in ()).throw(ValueError("boom")))
        result = dataset_info(path=str(csv_path))
        assert "Inspection failed" in result["error"]


class TestInspectHelpers:
    def test_inspect_tabular_shape(self, tmp_path):
        csv_path = tmp_path / "matrix.csv"
        pd.DataFrame({"c1": [1, 2], "c2": [3, 4]}, index=["g1", "g2"]).to_csv(csv_path)
        info = _inspect_tabular(csv_path, size_mb=0.01, sep=",")
        assert info["shape"] == [2, 2]
        assert "g1" in str(info["head_preview"])

    def test_inspect_h5ad_without_scanpy(self, tmp_path):
        h5ad = tmp_path / "data.h5ad"
        h5ad.write_bytes(b"fake")
        with patch("tools.omics._check_scanpy", return_value=None):
            info = _inspect_h5ad(h5ad, size_mb=0.1)
        assert info["file_type"] == "h5ad"
        assert "scanpy" in info["summary"]

    def test_inspect_h5ad_with_scanpy(self, tmp_path):
        h5ad = tmp_path / "data.h5ad"
        h5ad.write_bytes(b"fake")
        mock_adata = MagicMock()
        mock_adata.n_obs = 100
        mock_adata.n_vars = 50
        mock_adata.obs.columns = ["cell_type"]
        mock_adata.var.columns = ["gene_name"]
        mock_adata.layers = {}
        mock_adata.obs.__getitem__.return_value.unique.return_value = ["T cell"]
        mock_sc = MagicMock()
        mock_sc.read_h5ad.return_value = mock_adata
        with patch("tools.omics._check_scanpy", return_value=mock_sc):
            info = _inspect_h5ad(h5ad, size_mb=1.0)
        assert info["n_cells"] == 100
        assert info["n_genes"] == 50

    def test_dataset_info_h5ad_suffix(self, tmp_path):
        h5ad = tmp_path / "sample.h5ad"
        h5ad.write_bytes(b"fake")
        with patch("tools.omics._inspect_h5ad", return_value={"summary": "h5ad ok", "file_type": "h5ad"}):
            result = dataset_info(path=str(h5ad))
        assert result["file_type"] == "h5ad"

    def test_inspect_matrix_gz(self, tmp_path):
        gz_path = tmp_path / "series_matrix.txt.gz"
        content = (
            '!Series_title\t"RNA-seq study"\n'
            '!Series_organism\t"Homo sapiens"\n'
            '"ID_REF"\t"GSM1"\t"GSM2"\n'
            "1007_s_at\t1.0\t2.0\n"
            "1053_at\t3.0\t4.0\n"
        )
        with gzip.open(gz_path, "wt") as f:
            f.write(content)

        info = _inspect_matrix_gz(gz_path, size_mb=0.01)
        assert info["file_type"] == "matrix.txt.gz"
        assert info["n_samples"] == 2
        assert info["n_probes_or_genes"] == 2
        assert "RNA-seq study" in info["title"]


class TestRunKeggOraHelper:
    def test_run_kegg_ora_no_overlap(self):
        df = _run_kegg_ora(
            gene_ids={"geneA"},
            all_kegg_genes={"geneB"},
            path2genes={"path1": {"geneB"}},
            path_names={"path1": "Other pathway"},
        )
        assert df.empty

    def test_run_kegg_ora_significant_pathway(self):
        all_genes = {f"g{i}" for i in range(100)}
        path_genes = {f"g{i}" for i in range(10)}
        deg = {f"g{i}" for i in range(5)}
        df = _run_kegg_ora(
            gene_ids=deg,
            all_kegg_genes=all_genes,
            path2genes={"hsa00010": path_genes},
            path_names={"hsa00010": "Glycolysis"},
            min_size=5,
            max_size=50,
        )
        assert len(df) == 1
        assert df.iloc[0]["pathway"] == "hsa00010"
        assert df.iloc[0]["overlap"] == 5
        assert df.iloc[0]["padj"] <= df.iloc[0]["pvalue"]


class TestKeggOraTool:
    @patch("tools.code._generate_and_execute_code")
    def test_kegg_ora_delegates_to_code_gen(self, mock_exec):
        mock_exec.return_value = {"summary": "KEGG ORA complete", "answer": "hsa00010"}
        session = MagicMock()
        result = kegg_ora(goal="Run KEGG ORA for hsa DEGs", _session=session)
        assert result["summary"] == "KEGG ORA complete"
        mock_exec.assert_called_once()
        assert "KEGG" in mock_exec.call_args.kwargs["system_prompt_template"]


class TestDeseq2ErrorPaths:
    def _write_counts(self, tmp_path):
        counts = tmp_path / "counts.csv"
        pd.DataFrame(
            {
                "s1": [10, 20],
                "s2": [11, 21],
                "s3": [50, 60],
                "s4": [55, 65],
            },
            index=["GENE1", "GENE2"],
        ).to_csv(counts)
        return counts

    def test_missing_counts_file(self, tmp_path):
        result = deseq2(counts_path=str(tmp_path / "missing.csv"))
        assert "Could not load counts" in result["summary"]

    def test_metadata_required_without_infer(self, tmp_path):
        counts = self._write_counts(tmp_path)
        result = deseq2(counts_path=str(counts))
        assert "No metadata provided" in result["summary"]
        assert "metadata_path is required" in result["error"]

    def test_too_few_samples_with_infer(self, tmp_path):
        counts = tmp_path / "tiny.csv"
        pd.DataFrame({"s1": [1], "s2": [2], "s3": [3]}, index=["G1"]).to_csv(counts)
        result = deseq2(counts_path=str(counts), infer_metadata=True)
        assert "Too few samples" in result["summary"]

    @patch("tools.omics._check_pydeseq2", return_value=False)
    def test_missing_condition_column(self, _pydeseq, tmp_path):
        counts = self._write_counts(tmp_path)
        meta = tmp_path / "meta.csv"
        pd.DataFrame({"batch": ["a", "a", "b", "b"]}, index=["s1", "s2", "s3", "s4"]).to_csv(meta)
        result = deseq2(counts_path=str(counts), metadata_path=str(meta), use_r_deseq2=False)
        assert "Missing condition column" in result["summary"]

    @patch("tools.omics._check_pydeseq2", return_value=False)
    def test_too_few_shared_samples(self, _pydeseq, tmp_path):
        counts = self._write_counts(tmp_path)
        meta = tmp_path / "meta.csv"
        pd.DataFrame({"condition": ["control", "control"]}, index=["s1", "s2"]).to_csv(meta)
        result = deseq2(counts_path=str(counts), metadata_path=str(meta), use_r_deseq2=False)
        assert "Too few matching samples" in result["summary"]

    @patch("tools.omics._check_pydeseq2", return_value=False)
    def test_single_condition_level(self, _pydeseq, tmp_path):
        counts = self._write_counts(tmp_path)
        meta = tmp_path / "meta.csv"
        pd.DataFrame({"condition": ["control"] * 4}, index=["s1", "s2", "s3", "s4"]).to_csv(meta)
        result = deseq2(counts_path=str(counts), metadata_path=str(meta), use_r_deseq2=False)
        assert "Only one condition level" in result["summary"]

    @patch("tools.omics._check_pydeseq2", return_value=False)
    def test_invalid_contrast_levels(self, _pydeseq, tmp_path):
        counts = self._write_counts(tmp_path)
        meta = tmp_path / "meta.csv"
        pd.DataFrame({"condition": ["a", "a", "b", "b"]}, index=["s1", "s2", "s3", "s4"]).to_csv(meta)
        result = deseq2(
            counts_path=str(counts),
            metadata_path=str(meta),
            ref_level="missing",
            test_level="also_missing",
            use_r_deseq2=False,
        )
        assert "Invalid contrast levels" in result["summary"]

    @patch("tools.omics._check_pydeseq2", return_value=False)
    def test_missing_covariate_column(self, _pydeseq, tmp_path):
        counts = self._write_counts(tmp_path)
        meta = tmp_path / "meta.csv"
        pd.DataFrame({"condition": ["a", "a", "b", "b"]}, index=["s1", "s2", "s3", "s4"]).to_csv(meta)
        result = deseq2(
            counts_path=str(counts),
            metadata_path=str(meta),
            covariates="batch",
            use_r_deseq2=False,
        )
        assert "Missing covariates" in result["summary"]

    @patch("tools.omics._check_pydeseq2", return_value=False)
    def test_prefilter_removes_all_genes(self, _pydeseq, tmp_path):
        counts = self._write_counts(tmp_path)
        meta = tmp_path / "meta.csv"
        pd.DataFrame({"condition": ["a", "a", "b", "b"]}, index=["s1", "s2", "s3", "s4"]).to_csv(meta)
        result = deseq2(
            counts_path=str(counts),
            metadata_path=str(meta),
            prefilter_min_count=1000,
            use_r_deseq2=False,
        )
        assert "No genes left after prefilter" in result["summary"]

    @patch("tools.omics._check_pydeseq2", return_value=False)
    def test_insufficient_replicates(self, _pydeseq, tmp_path):
        counts = tmp_path / "counts.csv"
        pd.DataFrame({"s1": [1], "s2": [2], "s3": [3], "s4": [4]}, index=["G1"]).to_csv(counts)
        meta = tmp_path / "meta.csv"
        pd.DataFrame({"condition": ["a", "b", "b", "b"]}, index=["s1", "s2", "s3", "s4"]).to_csv(meta)
        result = deseq2(counts_path=str(counts), metadata_path=str(meta), use_r_deseq2=False)
        assert "Insufficient biological replicates" in result["summary"]


class TestSpatialCluster:
    def test_spatial_cluster_without_scanpy(self, tmp_path):
        from tools.omics import spatial_cluster

        h5ad = tmp_path / "spatial.h5ad"
        h5ad.write_bytes(b"fake")
        with patch("tools.omics._check_scanpy", return_value=None):
            result = spatial_cluster(path=str(h5ad))
        assert "Install scanpy" in result["summary"]

    def test_spatial_cluster_with_scanpy(self, tmp_path):
        from tools.omics import spatial_cluster

        h5ad = tmp_path / "spatial.h5ad"
        h5ad.write_bytes(b"fake")

        obs_series = MagicMock()
        obs_series.value_counts.return_value.to_dict.return_value = {"0": 2, "1": 1}
        obs_series.unique.return_value = ["0", "1"]
        mock_adata = MagicMock()
        mock_adata.n_obs = 200
        mock_adata.n_vars = 1000
        mock_adata.X.max.return_value = 100.0
        mock_adata.obsm = {"spatial": [[0, 0], [1, 1]]}
        mock_adata.obs.__getitem__.return_value = obs_series
        mock_adata.obsp = {"connectivities": MagicMock(), "spatial_connectivities": MagicMock()}
        mock_adata.uns = {"rank_genes_groups": {"names": {"0": ["GENE1"], "1": ["GENE2"]}}}

        mock_sc = MagicMock()
        mock_sc.read_h5ad.return_value = mock_adata

        with patch("tools.omics._check_scanpy", return_value=mock_sc), patch.dict(
            "sys.modules", {"squidpy": MagicMock()}
        ):
            result = spatial_cluster(path=str(h5ad), resolution=0.8, n_neighbors=10)

        assert result["n_clusters"] == 2
        assert result["used_squidpy"] is True
        assert "Spatial clustering" in result["summary"]
