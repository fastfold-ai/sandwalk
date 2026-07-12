"""Focused tests for combination therapy tools."""

from unittest.mock import patch

import numpy as np
import pandas as pd


def _model_df(n: int) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "CCLEName": [f"CCLE_{i}" for i in range(n)],
            "ModelID": [f"MODEL_{i}" for i in range(n)],
            "OncotreeLineage": [f"LIN_{i % 3}" for i in range(n)],
        }
    )


def test_synergy_predict_returns_empty_when_no_anticorrelated_pairs():
    from tools.combination import synergy_predict

    l1000 = pd.DataFrame(
        [[1.0, 2.0], [1.1, 2.1]],
        index=["cmpd_a", "cmpd_b"],
        columns=["G1", "G2"],
    )
    prism = pd.DataFrame(
        {
            "pert_name": ["cmpd_a", "cmpd_b"],
            "pert_dose": [10.0, 10.0],
            "ccle_name": ["CCLE_0", "CCLE_1"],
            "LFC": [-0.2, -0.1],
        }
    )
    model = _model_df(2)

    with patch("data.loaders.load_l1000", return_value=l1000), patch(
        "data.loaders.load_prism", return_value=prism
    ), patch("data.loaders.load_model_metadata", return_value=model), patch(
        "sklearn.metrics.pairwise.cosine_similarity",
        return_value=np.array([[1.0, 0.2], [0.2, 1.0]]),
    ):
        out = synergy_predict(compound_id="all", top_n=5)

    assert out["n_pairs"] == 0
    assert out["top_candidates"] == []


def test_synergy_predict_query_compound_mode_returns_candidates():
    from tools.combination import synergy_predict

    l1000 = pd.DataFrame(
        [[0.1, 0.2, 0.3], [0.3, 0.2, 0.1], [-0.2, -0.1, 0.0]],
        index=["cmpd_a", "cmpd_b", "cmpd_c"],
        columns=["G1", "G2", "G3"],
    )

    rows = []
    for cpd in ["cmpd_a", "cmpd_b", "cmpd_c"]:
        for i in range(6):
            rows.append(
                {
                    "pert_name": cpd,
                    "pert_dose": 10.0,
                    "ccle_name": f"CCLE_{i}",
                    "LFC": -0.6 + (i * 0.05),
                }
            )
    prism = pd.DataFrame(rows)
    model = _model_df(6)

    sim = np.array(
        [
            [1.0, -0.9, -0.45],
            [-0.9, 1.0, -0.2],
            [-0.45, -0.2, 1.0],
        ]
    )

    with patch("data.loaders.load_l1000", return_value=l1000), patch(
        "data.loaders.load_prism", return_value=prism
    ), patch("data.loaders.load_model_metadata", return_value=model), patch(
        "tools._compound_resolver.resolve_compound", return_value="cmpd_a"
    ), patch("sklearn.metrics.pairwise.cosine_similarity", return_value=sim):
        out = synergy_predict(compound_id="cmpd_a", top_n=3)

    assert out["n_pairs"] >= 1
    assert out["top_candidates"][0]["compound_1"] == "cmpd_a"
    assert "synergy_score" in out["top_candidates"][0]


def test_synthetic_lethality_missing_gene_and_strength_labels():
    from tools.combination import synthetic_lethality

    crispr = pd.DataFrame(
        {
            "TP53": np.linspace(-1.0, 0.5, 60),
            "GENE_A": np.linspace(0.5, -1.0, 60),
            "GENE_B": np.linspace(0.2, -0.6, 60),
            "GENE_C": np.linspace(0.0, 0.1, 60),
        },
        index=[f"MODEL_{i}" for i in range(60)],
    )

    with patch("data.loaders.load_crispr", return_value=crispr):
        miss = synthetic_lethality("NOT_PRESENT")
    assert "not found" in miss["error"]

    with patch("data.loaders.load_crispr", return_value=crispr), patch(
        "scipy.stats.pearsonr",
        side_effect=[(-0.35, 0.001), (-0.24, 0.01), (-0.15, 0.05)],
    ):
        out = synthetic_lethality("TP53", top_n=3)

    assert out["n_candidates"] == 3
    strengths = {row["strength"] for row in out["top_partners"]}
    assert {"strong", "moderate", "weak"} & strengths


def test_metabolic_vulnerability_handles_error_and_success_paths():
    from tools.combination import metabolic_vulnerability

    # No pathway gene coverage in L1000.
    l1000_no_pathway = pd.DataFrame(
        [[1.0, 2.0]],
        index=["cmpd_x"],
        columns=["NON_MET_A", "NON_MET_B"],
    )
    crispr = pd.DataFrame(
        {"HK1": [-1.0, -0.2], "HK2": [-0.8, -0.1]},
        index=["MODEL_0", "MODEL_1"],
    )
    prism = pd.DataFrame(
        {
            "pert_name": ["cmpd_x"],
            "pert_dose": [10.0],
            "ccle_name": ["CCLE_0"],
            "LFC": [-0.2],
        }
    )
    model = _model_df(2)

    with patch("data.loaders.load_l1000", return_value=l1000_no_pathway), patch(
        "data.loaders.load_crispr", return_value=crispr
    ), patch("data.loaders.load_prism", return_value=prism), patch(
        "data.loaders.load_model_metadata", return_value=model
    ):
        no_cov = metabolic_vulnerability(compound_id="all", pathway="all")
    assert "sufficient gene coverage" in no_cov["error"]

    # Valid pathway, enough overlap, exploit classification.
    l1000 = pd.DataFrame(
        [[-10.0, -10.0], [0.0, 0.0], [5.0, 5.0]],
        index=["cmpd_1", "cmpd_2", "cmpd_3"],
        columns=["HK1", "HK2"],
    )
    n = 30
    model = _model_df(n)
    crispr = pd.DataFrame(
        {
            "HK1": [-1.0] * 15 + [0.0] * 15,
            "HK2": [-0.9] * 15 + [0.1] * 15,
        },
        index=[f"MODEL_{i}" for i in range(n)],
    )
    prism = pd.DataFrame(
        {
            "pert_name": ["cmpd_1"] * n,
            "pert_dose": [10.0] * n,
            "ccle_name": [f"CCLE_{i}" for i in range(n)],
            "LFC": [-0.8] * 15 + [-0.2] * 15,
        }
    )

    with patch("data.loaders.load_l1000", return_value=l1000), patch(
        "data.loaders.load_crispr", return_value=crispr
    ), patch("data.loaders.load_prism", return_value=prism), patch(
        "data.loaders.load_model_metadata", return_value=model
    ), patch("tools._compound_resolver.resolve_compound", return_value="cmpd_1"), patch(
        "scipy.stats.ttest_ind", return_value=(2.1, 0.01)
    ):
        out = metabolic_vulnerability(compound_id="cmpd_1", pathway="glycolysis")

    assert out["n_total"] >= 1
    assert out["n_exploitable"] >= 1
    assert any(v["vulnerability_type"] == "EXPLOIT" for v in out["vulnerabilities"])
