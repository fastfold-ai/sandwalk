"""Tests for tools.omics pure helper functions."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd
import pytest

from tools.omics import (
    _check_scanpy,
    _downloads_dir,
    _enrichr_libraries_for_organism,
    _fdr_correct,
    _inspect_tabular,
    _load_tabular,
    _max_download_mb,
    _parse_gene_list_file,
    _parse_sample_groups,
    _stream_download,
    proteomics_enrich,
)


class TestFdrCorrect:
    def test_bh_correction(self):
        pvals = [0.01, 0.04, 0.03, 0.20, 0.50]
        adjusted = _fdr_correct(pvals)
        assert len(adjusted) == 5
        assert all(0 <= float(x) <= 1 for x in adjusted)


class TestParseSampleGroups:
    def test_explicit_groups(self):
        df = pd.DataFrame(
            {
                "control_1": [10, 20],
                "control_2": [11, 21],
                "treated_1": [50, 60],
                "treated_2": [55, 65],
            },
            index=["TP53", "BRCA1"],
        )
        g1, g2, err = _parse_sample_groups(
            df,
            group1="control_1,control_2",
            group2="treated_1,treated_2",
        )
        assert err is None
        assert g1 == ["control_1", "control_2"]
        assert g2 == ["treated_1", "treated_2"]

    def test_missing_groups_returns_error(self):
        df = pd.DataFrame({"s1": [1], "s2": [2]}, index=["gene1"])
        g1, g2, err = _parse_sample_groups(df)
        assert err is not None
        assert g1 == []


class TestParseGeneListFile:
    def test_reads_gene_symbols(self, tmp_path):
        path = tmp_path / "genes.txt"
        path.write_text("TP53\nBRCA1\nMYC\n")
        genes, error = _parse_gene_list_file(str(path))
        assert error is None
        assert genes == {"TP53", "BRCA1", "MYC"}

    def test_csv_tsv_and_empty_file_paths(self, tmp_path):
        csv_path = tmp_path / "genes.csv"
        pd.DataFrame({"gene": ["tp53", "brca1"]}).to_csv(csv_path, index=False)
        genes_csv, err_csv = _parse_gene_list_file(str(csv_path))
        assert err_csv is None
        assert genes_csv == {"TP53", "BRCA1"}

        tsv_path = tmp_path / "genes.tsv"
        pd.DataFrame({"gene": ["myc"]}).to_csv(tsv_path, sep="\t", index=False)
        genes_tsv, err_tsv = _parse_gene_list_file(str(tsv_path))
        assert err_tsv is None
        assert genes_tsv == {"MYC"}

        empty_csv = tmp_path / "empty.csv"
        pd.DataFrame(columns=["gene"]).to_csv(empty_csv, index=False)
        genes_empty, err_empty = _parse_gene_list_file(str(empty_csv))
        assert genes_empty == set()
        assert "empty" in err_empty.lower()

    def test_missing_and_parse_failure_paths(self, tmp_path):
        genes_missing, err_missing = _parse_gene_list_file(str(tmp_path / "missing.txt"))
        assert genes_missing == set()
        assert "not found" in err_missing.lower()

        bad_csv = tmp_path / "bad.csv"
        bad_csv.write_text("\x00\x00\x00", encoding="utf-8")
        with patch("pandas.read_csv", side_effect=ValueError("bad file")):
            genes_bad, err_bad = _parse_gene_list_file(str(bad_csv))
        assert genes_bad == set()
        assert "failed to parse" in err_bad.lower()


class TestEnrichrLibraries:
    def test_human_libraries(self):
        libs, error = _enrichr_libraries_for_organism("human")
        assert error is None
        assert "GO_Biological_Process_2023" in libs

    def test_unsupported_organism(self):
        libs, error = _enrichr_libraries_for_organism("zebrafish")
        assert libs is None
        assert "Unsupported" in error

    def test_mouse_libraries(self):
        libs, error = _enrichr_libraries_for_organism("mouse")
        assert error is None
        assert "KEGG_2021_Mouse" in libs


class TestLoadTabular:
    def test_csv_and_tsv(self, tmp_path):
        csv_path = tmp_path / "data.csv"
        pd.DataFrame({"gene": ["TP53"], "value": [1.0]}).to_csv(csv_path, index=False)
        df, err = _load_tabular(str(csv_path), index_col=None)
        assert err is None
        assert df.iloc[0]["gene"] == "TP53"

        tsv_path = tmp_path / "data.tsv"
        pd.DataFrame({"gene": ["BRCA1"], "value": [2.0]}).to_csv(tsv_path, sep="\t", index=False)
        df2, err2 = _load_tabular(str(tsv_path), index_col=None)
        assert err2 is None
        assert df2.iloc[0]["gene"] == "BRCA1"

    def test_missing_file(self, tmp_path):
        df, err = _load_tabular(str(tmp_path / "missing.csv"))
        assert df is None
        assert "not found" in err.lower()


class TestInspectTabular:
    def test_inspect_csv(self, tmp_path):
        csv_path = tmp_path / "sample.csv"
        pd.DataFrame({"gene": ["TP53"], "value": [1.0]}).to_csv(csv_path, index=False)
        info = _inspect_tabular(csv_path, size_mb=0.01)
        assert info["file_type"] == "csv"
        assert "value" in info["columns"]


class TestDownloadAndConfigHelpers:
    def test_downloads_dir_and_max_download_from_config(self, tmp_path):
        fake_cfg = SimpleNamespace(
            get=lambda key, default=None: (
                str(tmp_path / "downloads") if key == "data.downloads_dir" else 321
            )
        )
        with patch("agent.config.Config.load", return_value=fake_cfg):
            d = _downloads_dir()
            max_mb = _max_download_mb()
        assert d.exists()
        assert d == tmp_path / "downloads"
        assert max_mb == 321

    def test_check_scanpy_unavailable(self):
        with patch("builtins.__import__", side_effect=ImportError("no scanpy")):
            assert _check_scanpy() is None

    def test_stream_download_size_and_success_paths(self, tmp_path):
        dest = tmp_path / "file.bin"

        class _Resp:
            def __init__(self, chunks, content_length=None):
                self._chunks = chunks
                self.headers = {}
                if content_length is not None:
                    self.headers["content-length"] = str(content_length)

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def raise_for_status(self):
                return None

            def iter_bytes(self, chunk_size=65536):
                del chunk_size
                for c in self._chunks:
                    yield c

        # Content-length too large.
        with patch("httpx.stream", return_value=_Resp([], content_length=10_000_000)):
            out, err = _stream_download("https://example.com/a", dest, max_mb=1)
        assert out is None
        assert "exceeds limit" in err

        # Stream exceeds size while downloading.
        with patch("httpx.stream", return_value=_Resp([b"x" * (2 * 1024 * 1024)])):
            out2, err2 = _stream_download("https://example.com/b", dest, max_mb=1)
        assert out2 is None
        assert "exceeded size limit" in err2

        # Successful download.
        with patch("httpx.stream", return_value=_Resp([b"abc", b"def"], content_length=6)):
            out3, err3 = _stream_download("https://example.com/c", dest, max_mb=1)
        assert err3 is None
        assert out3 == dest
        assert dest.read_bytes() == b"abcdef"

    def test_stream_download_http_and_generic_error_paths(self, tmp_path):
        import httpx

        dest = tmp_path / "x.bin"

        class _HttpErrResp:
            status_code = 404

        class _HttpErrCtx:
            def __enter__(self):
                raise httpx.HTTPStatusError("not found", request=None, response=_HttpErrResp())

            def __exit__(self, exc_type, exc, tb):
                return False

        with patch("httpx.stream", return_value=_HttpErrCtx()):
            out, err = _stream_download("https://example.com/404", dest, max_mb=1)
        assert out is None
        assert "HTTP 404" in err

        with patch("httpx.stream", side_effect=RuntimeError("boom")):
            out2, err2 = _stream_download("https://example.com/err", dest, max_mb=1)
        assert out2 is None
        assert "Download failed" in err2


class TestProteomicsEnrichEarlyBranches:
    def test_early_validation_paths(self, tmp_path):
        out_empty = proteomics_enrich(proteins="")
        assert "error" in out_empty

        out_org = proteomics_enrich(proteins="TP53", organism="zebrafish")
        assert "Unsupported organism" in out_org["error"]

        out_bg_missing = proteomics_enrich(proteins="TP53", background_path=str(tmp_path / "missing.txt"))
        assert "Background file not found" in out_bg_missing["error"]

        empty_bg = tmp_path / "empty.txt"
        empty_bg.write_text("", encoding="utf-8")
        out_bg_empty = proteomics_enrich(proteins="TP53", background_path=str(empty_bg))
        assert "contains no genes" in out_bg_empty["error"]
