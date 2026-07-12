"""Additional path coverage for tools.omics fetch/search flows."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from tools.omics import geo_fetch, geo_search, tcga_fetch, tcga_search


class TestGeoAdditionalBranches:
    @patch("tools.omics.request_json")
    def test_geo_search_summary_fetch_error(self, mock_request_json):
        mock_request_json.side_effect = [
            ({"esearchresult": {"idlist": ["1"]}}, None),
            ({}, "summary down"),
        ]
        out = geo_search("TP53")
        assert "error" in out
        assert "summary" in out["error"].lower()

    @patch("tools.omics.request")
    def test_geo_fetch_h5ad_missing_in_supp_files(self, mock_request):
        mock_resp = MagicMock()
        mock_resp.text = '<a href="file1.txt.gz">file1.txt.gz</a>'
        mock_request.return_value = (mock_resp, None)
        out = geo_fetch("GSE12345", file_type="h5ad")
        assert "error" in out
        assert "No h5ad files found" in out["error"]

    @patch("tools.omics.request")
    def test_geo_fetch_supp_listing_error(self, mock_request):
        mock_request.return_value = (None, "network timeout")
        out = geo_fetch("GSE12345", file_type="supplementary")
        assert "error" in out
        assert "listing" in out["summary"].lower()


class TestTcgaAdditionalBranches:
    @patch("tools.omics.request_json")
    def test_tcga_search_api_error(self, mock_request_json):
        mock_request_json.return_value = ({}, "gdc unavailable")
        out = tcga_search("BRCA")
        assert "error" in out
        assert "GDC" in out["summary"]

    @patch("tools.omics.request_json")
    def test_tcga_fetch_project_search_error(self, mock_request_json):
        mock_request_json.return_value = ({}, "api error")
        out = tcga_fetch(project_id="TCGA-BRCA")
        assert "error" in out
        assert "search" in out["summary"].lower()

    @patch("tools.omics._downloads_dir")
    def test_tcga_fetch_existing_file_short_circuit(self, mock_downloads_dir, tmp_path):
        file_id = "abc123"
        target_dir = tmp_path / "tcga" / file_id[:12]
        target_dir.mkdir(parents=True, exist_ok=True)
        existing = target_dir / f"{file_id}.gz"
        existing.write_text("already here", encoding="utf-8")
        mock_downloads_dir.return_value = tmp_path

        out = tcga_fetch(file_id=file_id)
        assert out["file_id"] == file_id
        assert "Already downloaded" in out["summary"]
        assert Path(out["path"]).exists()
