"""Tests for repurposing tools."""

from unittest.mock import patch

import pandas as pd


class TestRepurposingCmapQuery:
    def test_remote_fallback_returns_hits_when_l1000_missing(self):
        from tools.repurposing import cmap_query

        with patch("data.loaders.load_l1000", side_effect=FileNotFoundError("missing")):
            with patch("tools.repurposing.request_json") as mock_request_json:
                mock_request_json.side_effect = [
                    ({"result_id": "abc123"}, None),
                    (
                        {
                            "similar": [
                                {"pert_iname": "drug_a", "score": 0.91},
                                {"pert_iname": "drug_b", "score": 0.88},
                            ],
                            "opposite": [
                                {"pert_iname": "drug_x", "score": -0.93},
                                {"pert_iname": "drug_y", "score": -0.90},
                            ],
                        },
                        None,
                    ),
                ]

                result = cmap_query(
                    gene_signature={
                        "TNF": 2.5,
                        "IL1B": 2.1,
                        "IL10": -1.3,
                        "MUC2": -1.1,
                    },
                    mode="reverse",
                    top_n=10,
                )

        assert "error" not in result
        assert result["remote_used"] is True
        assert result["remote_source"] == "L1000FWD"
        assert result["local_data_unavailable"] is True
        assert len(result["hits"]) == 2
        assert result["hits"][0]["compound"] == "drug_x"
        assert "Remote CMap query via L1000FWD" in result["summary"]

    @patch("data.loaders.load_l1000", side_effect=FileNotFoundError("missing"))
    @patch("tools.repurposing.request_json", return_value=(None, "HTTP 503"))
    def test_marks_data_unavailable_when_remote_fallback_fails(self, _mock_request_json, _mock_l1000):
        from tools.repurposing import cmap_query

        result = cmap_query(
            gene_signature={
                "TNF": 2.5,
                "IL1B": 2.1,
                "IL10": -1.3,
                "MUC2": -1.1,
            },
            mode="reverse",
            top_n=10,
        )

        assert "error" not in result
        assert result["data_unavailable"] is True
        assert result["remote_used"] is False
        assert "remote_error" in result
        assert result["hits"] == []
        assert len(result["up_genes"]) == 2
        assert len(result["down_genes"]) == 2
        assert "cannot compute correlations locally" in result["summary"]

    @patch("data.loaders.load_l1000", side_effect=FileNotFoundError("missing"))
    @patch("tools.repurposing.request_json")
    def test_no_remote_call_when_allow_remote_false(self, mock_request_json, _mock_l1000):
        from tools.repurposing import cmap_query

        result = cmap_query(
            gene_signature={
                "TNF": 2.5,
                "IL1B": 2.1,
                "IL10": -1.3,
                "MUC2": -1.1,
            },
            mode="reverse",
            top_n=10,
            allow_remote=False,
        )

        mock_request_json.assert_not_called()
        assert result["data_unavailable"] is True
        assert result["remote_used"] is False

    def test_local_compound_mode_returns_ranked_hits(self):
        from tools.repurposing import cmap_query

        # 12 genes ensures valid overlap path for local correlations.
        genes = [f"G{i}" for i in range(12)]
        l1000 = pd.DataFrame(
            [
                [i for i in range(12)],            # cmpd_a
                [i * 1.1 for i in range(12)],      # cmpd_b (similar)
                [11 - i for i in range(12)],       # cmpd_c (reverse-ish)
            ],
            index=["cmpd_a", "cmpd_b", "cmpd_c"],
            columns=genes,
        )

        with patch("data.loaders.load_l1000", return_value=l1000):
            out = cmap_query(compound_id="cmpd_a", mode="similar", top_n=2)

        assert out["n_compounds_screened"] >= 2
        assert len(out["hits"]) == 2
        assert out["hits"][0]["strength"] in {"strong", "moderate", "weak"}
        assert "CMap query" in out["summary"]

    def test_invalid_inputs_and_compound_not_found(self):
        from tools.repurposing import cmap_query

        assert "error" in cmap_query()
        bad_mode = cmap_query(gene_signature={"TP53": 1.0}, mode="bad-mode")
        assert "Unknown mode" in bad_mode["error"]

        l1000 = pd.DataFrame([[1.0, 2.0]], index=["cmpd_x"], columns=["G1", "G2"])
        with patch("data.loaders.load_l1000", return_value=l1000):
            miss = cmap_query(compound_id="not_here")
        assert "not found in L1000" in miss["error"]

    def test_remote_helper_and_extraction_utilities(self):
        from tools.repurposing import (
            _extract_l1000fwd_hits,
            _normalize_l1000fwd_hit,
            _query_l1000fwd,
        )

        # Payload extraction across direct + nested keys.
        assert _extract_l1000fwd_hits([{"id": 1}], mode="similar") == [{"id": 1}]
        assert _extract_l1000fwd_hits({"results": {"reverse": [{"id": 2}]}}, mode="reverse") == [{"id": 2}]
        assert _extract_l1000fwd_hits({"x": 1}, mode="similar") == []

        normalized = _normalize_l1000fwd_hit({"pert_iname": "drug_a", "score": "0.42", "pval": "0.01"}, 1)
        assert normalized["compound"] == "drug_a"
        assert normalized["connectivity_score"] == 0.42
        assert normalized["p_value"] == 0.01
        assert _normalize_l1000fwd_hit("raw-hit", 3)["compound"] == "raw-hit"

        # Query helper errors and success path.
        with patch(
            "tools.repurposing.request_json",
            return_value=(None, "network down"),
        ):
            hits, err = _query_l1000fwd(["TNF"], ["IL10"], mode="similar", top_n=5)
        assert hits == []
        assert "sig_search failed" in err

        with patch(
            "tools.repurposing.request_json",
            side_effect=[({"result_id": "abc"}, None), ({"similar": [{"pert_iname": "d1", "score": 0.9}]}, None)],
        ):
            hits, err = _query_l1000fwd(["TNF"], ["IL10"], mode="similar", top_n=5)
        assert err is None
        assert hits[0]["compound"] == "d1"
