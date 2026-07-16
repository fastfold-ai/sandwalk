"""Unit tests for network biology gene-list helpers."""

from tools.network_common import _coerce_gene_list


def test_coerce_gene_list_none_and_empty():
    assert _coerce_gene_list(None) == []
    assert _coerce_gene_list("") == []
    assert _coerce_gene_list("  ,  ; ") == []


def test_coerce_gene_list_delimited_string():
    assert _coerce_gene_list("TP53, BRCA1; EGFR\nMYC|KRAS") == [
        "TP53",
        "BRCA1",
        "EGFR",
        "MYC",
        "KRAS",
    ]


def test_coerce_gene_list_collections_and_dedupe():
    assert _coerce_gene_list(["TP53", None, " BRCA1 ", "TP53"]) == ["TP53", "BRCA1"]
    assert _coerce_gene_list(("A", "B")) == ["A", "B"]
    assert _coerce_gene_list({"Z"}) == ["Z"]


def test_coerce_gene_list_scalar():
    assert _coerce_gene_list(42) == ["42"]
