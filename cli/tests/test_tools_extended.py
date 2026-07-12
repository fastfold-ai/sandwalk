"""Extended mocked tests for low-coverage tool modules."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest


# ─── Biomarker tools ──────────────────────────────────────────


class TestBiomarkerMutationSensitivity:
    @patch("tools._compound_resolver.resolve_compound", side_effect=lambda x, **k: x)
    @patch("data.loaders.load_model_metadata")
    @patch("data.loaders.load_mutations")
    @patch("data.loaders.load_prism")
    def test_finds_sensitizing_mutation(self, mock_prism, mock_mut, mock_model, _resolve):
        from tools.biomarker import mutation_sensitivity

        n = 30
        cells = [f"CELL{i}" for i in range(n)]
        model_ids = [f"ACH-{i:06d}" for i in range(n)]
        mock_model.return_value = pd.DataFrame({"CCLEName": cells, "ModelID": model_ids})

        tp53 = np.array([1] * 10 + [0] * 20)
        mock_mut.return_value = pd.DataFrame({"TP53": tp53}, index=model_ids)

        lfc = [float(np.random.uniform(-1.2, -0.7)) if tp53[i] else float(np.random.uniform(-0.2, 0.2)) for i in range(n)]
        mock_prism.return_value = pd.DataFrame({
            "pert_name": ["cpd_A"] * n,
            "pert_dose": [10.0] * n,
            "ccle_name": cells,
            "LFC": lfc,
        })

        result = mutation_sensitivity(compound_id="cpd_A", gene="TP53")
        assert "summary" in result
        assert result["compound"] == "cpd_A"
        assert result["n_tested"] >= 1

    @patch("tools._compound_resolver.resolve_compound", side_effect=lambda x, **k: x)
    @patch("data.loaders.load_model_metadata")
    @patch("data.loaders.load_mutations")
    @patch("data.loaders.load_prism")
    def test_compound_not_found(self, mock_prism, mock_mut, mock_model, _resolve):
        from tools.biomarker import mutation_sensitivity

        mock_model.return_value = pd.DataFrame({"CCLEName": [], "ModelID": []})
        mock_mut.return_value = pd.DataFrame(index=[])
        mock_prism.return_value = pd.DataFrame(columns=["pert_name", "pert_dose", "ccle_name", "LFC"])
        result = mutation_sensitivity(compound_id="missing_cpd")
        assert "error" in result
        assert "not found in PRISM" in result["summary"]


class TestBiomarkerResistanceProfile:
    @patch("tools._compound_resolver.resolve_compound", side_effect=lambda x, **k: x)
    @patch("data.loaders.load_model_metadata")
    @patch("data.loaders.load_prism")
    def test_profiles_lineages(self, mock_prism, mock_model, _resolve):
        from tools.biomarker import resistance_profile

        mock_model.return_value = pd.DataFrame({
            "CCLEName": ["A", "B", "C", "D"],
            "ModelID": ["m1", "m2", "m3", "m4"],
            "OncotreeLineage": ["Lymphoid", "Lymphoid", "Myeloid", "Myeloid"],
        })
        mock_prism.return_value = pd.DataFrame({
            "pert_name": ["cpd_B"] * 4,
            "pert_dose": [10.0] * 4,
            "ccle_name": ["A", "B", "C", "D"],
            "LFC": [-0.8, -0.7, 0.1, 0.2],
        })

        result = resistance_profile(compound_id="cpd_B")
        assert result["n_sensitive"] == 2
        assert result["n_resistant"] == 2
        assert "lineage_profiles" in result


# ─── Combination tools ────────────────────────────────────────


class TestCombinationSynergyPredict:
    @patch("tools._compound_resolver.resolve_compound", side_effect=lambda x, **k: x)
    @patch("data.loaders.load_model_metadata")
    @patch("data.loaders.load_prism")
    @patch("data.loaders.load_l1000")
    def test_finds_anticorrelated_pair(self, mock_l1000, mock_prism, mock_model, _resolve, monkeypatch):
        import sys
        from unittest.mock import MagicMock

        mock_pairwise = MagicMock()
        mock_pairwise.cosine_similarity = MagicMock(
            return_value=np.array([[1.0, -0.9], [-0.9, 1.0]])
        )
        mock_metrics = MagicMock(pairwise=mock_pairwise)
        monkeypatch.setitem(sys.modules, "sklearn", MagicMock(metrics=mock_metrics))
        monkeypatch.setitem(sys.modules, "sklearn.metrics", mock_metrics)
        monkeypatch.setitem(sys.modules, "sklearn.metrics.pairwise", mock_pairwise)

        from tools.combination import synergy_predict

        mock_l1000.return_value = pd.DataFrame(
            [[1.0, -1.0], [-1.0, 1.0]],
            index=["cpd_A", "cpd_B"],
            columns=["G1", "G2"],
        )
        mock_model.return_value = pd.DataFrame({
            "CCLEName": ["C1", "C2"],
            "OncotreeLineage": ["LineageA", "LineageB"],
        })
        mock_prism.return_value = pd.DataFrame({
            "pert_name": ["cpd_A", "cpd_A", "cpd_B", "cpd_B"],
            "pert_dose": [10.0, 10.0, 10.0, 10.0],
            "ccle_name": ["C1", "C2", "C1", "C2"],
            "LFC": [-0.8, -0.1, -0.1, -0.8],
        })

        result = synergy_predict(compound_id="cpd_A", top_n=5)
        assert "summary" in result
        assert result["n_pairs"] >= 0


class TestCombinationSyntheticLethality:
    @patch("data.loaders.load_crispr")
    def test_finds_anticorrelated_genes(self, mock_crispr):
        from tools.combination import synthetic_lethality

        np.random.seed(0)
        n = 60
        a = np.random.randn(n)
        b = -0.5 * a + np.random.randn(n) * 0.1
        mock_crispr.return_value = pd.DataFrame({"BRAF": a, "PARTNER1": b, "NOISE": np.random.randn(n)})

        result = synthetic_lethality(gene="BRAF", top_n=5)
        assert result["target_gene"] == "BRAF"
        assert result["n_candidates"] >= 1

    @patch("data.loaders.load_crispr")
    def test_missing_gene(self, mock_crispr):
        from tools.combination import synthetic_lethality

        mock_crispr.return_value = pd.DataFrame({"EGFR": [0.1, 0.2]})
        result = synthetic_lethality(gene="BRAF")
        assert "error" in result


class TestCombinationMetabolicVulnerability:
    @patch("tools._compound_resolver.resolve_compound", side_effect=lambda x, **k: x)
    @patch("data.loaders.load_model_metadata")
    @patch("data.loaders.load_prism")
    @patch("data.loaders.load_crispr")
    @patch("data.loaders.load_l1000")
    def test_pathway_scoring(self, mock_l1000, mock_crispr, mock_prism, mock_model, _resolve):
        from tools.combination import metabolic_vulnerability

        genes = ["HK2", "GAPDH", "PKM"]
        mock_l1000.return_value = pd.DataFrame(
            np.random.randn(3, 3),
            index=["cpd_X", "cpd_Y", "cpd_Z"],
            columns=genes,
        )
        mock_crispr.return_value = pd.DataFrame(
            np.random.randn(5, 3),
            columns=genes,
        )
        mock_prism.return_value = pd.DataFrame({
            "pert_name": ["cpd_X"] * 4,
            "pert_dose": [10.0] * 4,
            "ccle_name": ["C1", "C2", "C3", "C4"],
            "LFC": [-0.6, -0.5, 0.1, 0.2],
        })
        mock_model.return_value = pd.DataFrame({
            "CCLEName": ["C1", "C2", "C3", "C4"],
            "OncotreeLineage": ["A", "A", "B", "B"],
        })

        result = metabolic_vulnerability(compound_id="cpd_X", pathway="glycolysis")
        assert "summary" in result or "error" in result


# ─── Repurposing helpers and cmap_query ───────────────────────


class TestRepurposingHelpers:
    def test_to_float(self):
        from tools.repurposing import _to_float

        assert _to_float("1.5") == 1.5
        assert _to_float(None) is None
        assert _to_float("bad") is None

    def test_extract_l1000fwd_hits_reverse(self):
        from tools.repurposing import _extract_l1000fwd_hits

        payload = {"opposite": [{"pert_iname": "drug_a"}]}
        assert _extract_l1000fwd_hits(payload, "reverse") == payload["opposite"]

    def test_extract_l1000fwd_hits_nested(self):
        from tools.repurposing import _extract_l1000fwd_hits

        payload = {"results": {"similar": [{"name": "x"}]}}
        assert _extract_l1000fwd_hits(payload, "similar") == [{"name": "x"}]

    def test_normalize_l1000fwd_hit(self):
        from tools.repurposing import _normalize_l1000fwd_hit

        hit = _normalize_l1000fwd_hit({"pert_iname": "aspirin", "score": "0.88"}, rank=1)
        assert hit["compound"] == "aspirin"
        assert hit["connectivity_score"] == pytest.approx(0.88)

    @patch("tools.repurposing.request_json")
    def test_query_l1000fwd_success(self, mock_request):
        from tools.repurposing import _query_l1000fwd

        mock_request.side_effect = [
            ({"result_id": "rid123"}, None),
            ({"similar": [{"pert_iname": "drug_a", "score": 0.9}]}, None),
        ]
        hits, err = _query_l1000fwd(["TNF"], ["IL10"], mode="similar", top_n=5)
        assert err is None
        assert hits[0]["compound"] == "drug_a"

    @patch("data.loaders.load_l1000")
    def test_cmap_query_with_local_l1000(self, mock_l1000):
        from tools.repurposing import cmap_query

        mock_l1000.return_value = pd.DataFrame(
            [[1.0, 0.5], [0.9, 0.4], [-0.8, -0.3]],
            index=["query_cpd", "similar_cpd", "reverse_cpd"],
            columns=["G1", "G2"],
        )
        result = cmap_query(compound_id="query_cpd", mode="similar", top_n=2)
        assert "hits" in result
        assert len(result["hits"]) <= 2
        assert "summary" in result


# ─── Skills tool wrapper ──────────────────────────────────────


class TestSkillsManage:
    @patch("agent.skills.list_skills")
    def test_list_action(self, mock_list):
        from tools.skills import manage

        skill = MagicMock()
        skill.name = "fold"
        skill.source = "bundled"
        skill.description = "Folding skill"
        mock_list.return_value = [skill]

        result = manage(action="list")
        assert "fold" in result["summary"]
        assert result["skills"] == ["fold"]

    @patch("agent.skills.discover_skills")
    def test_find_action(self, mock_discover):
        from tools.skills import manage

        mock_discover.return_value = [
            {"name": "md-openmm", "install_source": "fastfold-ai/skills", "description": "MD workflows"},
        ]
        result = manage(action="find", query="md")
        assert "md-openmm" in result["summary"]

    @patch("agent.skills.skill_info")
    def test_info_missing_skill(self, mock_info):
        from tools.skills import manage

        mock_info.return_value = None
        result = manage(action="info", name="missing")
        assert "not installed" in result["summary"]

    def test_install_blocked_without_permission(self):
        from tools.skills import manage

        session = MagicMock()
        session.config.get.return_value = False
        result = manage(action="install", source="some/skill", _session=session)
        assert result["blocked"] is True
        assert result["ok"] is False

    @patch("agent.skills.install_skill")
    def test_install_allowed(self, mock_install):
        from tools.skills import manage

        session = MagicMock()
        session.config.get.return_value = True
        mock_install.return_value = {"summary": "Installed fold", "ok": True}
        result = manage(action="install", source="fold", _session=session)
        assert result["ok"] is True
        mock_install.assert_called_once_with("fold")

    def test_unknown_action(self):
        from tools.skills import manage

        result = manage(action="bogus")
        assert "Unknown action" in result["summary"]


# ─── Report pharma_brief ──────────────────────────────────────


class TestReportPharmaBriefExtended:
    def test_missing_query(self):
        from tools.report import pharma_brief

        result = pharma_brief(query="")
        assert result["error"] == "missing_query"

    def test_slug_and_evidence_extraction(self, tmp_path):
        from tools.report import _extract_evidence_lines, _slug, pharma_brief

        assert _slug("IL23R / UC Strategy!!!") == "il23r_uc_strategy"
        lines = _extract_evidence_lines({"summary": "Main finding", "key_evidence": ["A", "B"]})
        assert "Main finding" in lines
        assert "A" in lines

        class _Cfg:
            def get(self, key, default=None):
                if key == "sandbox.output_dir":
                    return str(tmp_path)
                return default

        class _Session:
            config = _Cfg()

        with patch("reports.html.publish_report", return_value=tmp_path / "out.html"):
            result = pharma_brief(
                query="KRAS G12C program",
                program_thesis="Prioritize sotorasib-adjacent differentiation.",
                evidence="Line one\nLine two",
                _session=_Session(),
                publish_html=True,
            )

        assert result["markdown_path"] is not None
        assert Path(result["markdown_path"]).exists()
        assert "KRAS G12C" in result["markdown"]

    def test_no_save_returns_markdown_only(self):
        from tools.report import pharma_brief

        result = pharma_brief(
            query="Quick brief",
            program_thesis="Go",
            save=False,
            publish_html=False,
        )
        assert result["markdown_path"] is None
        assert "Quick brief" in result["markdown"]
