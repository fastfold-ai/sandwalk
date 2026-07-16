"""Shared helpers for network biology tools (STRING/Reactome)."""


def _coerce_gene_list(value) -> list[str]:
    """Normalize gene input from str/list/tuple/set into a clean symbol list."""
    if value is None:
        return []

    items = []
    if isinstance(value, str):
        # Accept comma, semicolon, newline, or pipe separated strings.
        for chunk in value.replace("\n", ",").replace(";", ",").replace("|", ",").split(","):
            token = str(chunk).strip()
            if token:
                items.append(token)
    elif isinstance(value, (list, tuple, set)):
        for entry in value:
            if entry is None:
                continue
            token = str(entry).strip()
            if token:
                items.append(token)
    else:
        token = str(value).strip()
        if token:
            items.append(token)

    # De-duplicate while preserving order.
    seen = set()
    genes = []
    for gene in items:
        if gene in seen:
            continue
        seen.add(gene)
        genes.append(gene)
    return genes
