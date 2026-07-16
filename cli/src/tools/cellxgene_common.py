"""Shared helpers for CELLxGENE Census tools."""


def _check_census_sdk():
    """Check if cellxgene-census SDK is installed. Returns error dict or None."""
    try:
        import cellxgene_census  # noqa: F401

        return None
    except ImportError:
        return {
            "error": "cellxgene-census not installed.",
            "summary": (
                "cellxgene-census SDK required but not installed. "
                "Install with: pip install 'fastfold-agent-cli[singlecell]' "
                "or: pip install cellxgene-census"
            ),
        }
