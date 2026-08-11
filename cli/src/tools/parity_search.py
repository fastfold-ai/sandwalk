"""parity: PDBe/Reactome/preprint search tools.

Split from tools/parity.py. Calls ``request``/``request_json`` indirectly via
the ``tools.parity`` hub module so that ``patch("tools.parity.request_json")``
/ ``patch("tools.parity.request")`` in tests continue to work regardless of
which submodule performs the call.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

from tools import parity as _parity
from tools import registry
from tools.parity_common import _clip, _coerce_int


@registry.register(
    name="data_api.pdbe_search",
    description="Search PDBe entries by keyword",
    category="data_api",
    parameters={
        "query": "PDBe keyword query (protein, ligand, organism, etc.)",
        "size": "Maximum hits (default 10)",
    },
    usage_guide="Use when you need PDBe-centric structure records and metadata.",
)
def pdbe_search(query: str, size: int = 10, **kwargs) -> dict:
    """Search PDBe Solr endpoint for structure entries."""
    q = (query or "").strip()
    if not q:
        return {"summary": "query is required.", "error": "missing_query"}

    params = {
        "q": q,
        "wt": "json",
        "rows": _coerce_int(size, 10),
        "fl": "pdb_id,title,experimental_method,resolution,organism_scientific_name",
    }
    data, error = _parity.request_json(
        "GET",
        "https://www.ebi.ac.uk/pdbe/search/pdb/select",
        params=params,
        timeout=20,
        retries=2,
    )
    if error:
        return {"summary": f"PDBe search failed: {error}", "error": "api_error"}

    docs = []
    if isinstance(data, dict):
        docs = ((data.get("response") or {}).get("docs") or [])
    rows = []
    for doc in docs:
        if not isinstance(doc, dict):
            continue
        rows.append(
            {
                "pdb_id": doc.get("pdb_id"),
                "title": doc.get("title"),
                "experimental_method": doc.get("experimental_method"),
                "resolution": doc.get("resolution"),
                "organism": doc.get("organism_scientific_name"),
            }
        )

    return {
        "summary": f"PDBe: found {len(rows)} entries for '{q}'.",
        "query": q,
        "entries": rows,
        "count": len(rows),
        "source": "pdbe",
    }


@registry.register(
    name="data_api.reactome_pathway_search",
    description="Search Reactome pathways by keyword",
    category="data_api",
    parameters={
        "query": "Pathway or gene keyword",
        "size": "Maximum hits (default 10)",
    },
    usage_guide="Use to identify curated Reactome pathways related to a query.",
)
def reactome_pathway_search(query: str, size: int = 10, **kwargs) -> dict:
    """Search Reactome content service for pathways."""
    q = (query or "").strip()
    if not q:
        return {"summary": "query is required.", "error": "missing_query"}

    data, error = _parity.request_json(
        "GET",
        "https://reactome.org/ContentService/search/query",
        params={"query": q, "types": "Pathway", "cluster": "true"},
        timeout=20,
        retries=2,
    )
    if error:
        return {"summary": f"Reactome search failed: {error}", "error": "api_error"}

    results = []
    if isinstance(data, list):
        results = data
    elif isinstance(data, dict):
        results = data.get("results") or data.get("entries") or []

    rows = []
    for item in results[: _coerce_int(size, 10)]:
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "st_id": item.get("stId") or item.get("id"),
                "name": item.get("name") or item.get("displayName"),
                "species": item.get("species") or item.get("speciesName"),
                "type": item.get("type"),
                "url": (
                    f"https://reactome.org/content/detail/{item.get('stId')}"
                    if item.get("stId")
                    else None
                ),
            }
        )

    return {
        "summary": f"Reactome: found {len(rows)} pathway hits for '{q}'.",
        "query": q,
        "pathways": rows,
        "count": len(rows),
        "source": "reactome",
    }


@registry.register(
    name="literature.preprint_search",
    description="Search preprints across Europe PMC (bioRxiv/medRxiv) and arXiv",
    category="literature",
    parameters={
        "query": "Search query",
        "source": "Data source: europepmc, arxiv, or both (default both)",
        "max_results": "Maximum results (default 10)",
    },
    usage_guide="Use when you need latest preprint evidence that may not yet appear in PubMed.",
)
def preprint_search(query: str, source: str = "both", max_results: int = 10, **kwargs) -> dict:
    """Search preprints using EuropePMC and/or arXiv."""
    q = (query or "").strip()
    if not q:
        return {"summary": "query is required.", "error": "missing_query"}

    source_norm = str(source or "both").strip().lower()
    if source_norm not in {"both", "europepmc", "arxiv"}:
        return {"summary": "Invalid source. Use europepmc, arxiv, or both.", "error": "invalid_source"}

    limit = _coerce_int(max_results, 10, minimum=1, maximum=50)
    rows = []

    if source_norm in {"both", "europepmc"}:
        epmc_data, epmc_error = _parity.request_json(
            "GET",
            "https://www.ebi.ac.uk/europepmc/webservices/rest/search",
            params={
                "query": f"({q}) AND SRC:PPR",
                "format": "json",
                "pageSize": limit,
            },
            timeout=20,
            retries=2,
        )
        if epmc_error is None and isinstance(epmc_data, dict):
            result_list = (((epmc_data.get("resultList") or {}).get("result")) or [])
            for item in result_list:
                if not isinstance(item, dict):
                    continue
                title = item.get("title") or item.get("bookOrReportDetails", {}).get("title") if isinstance(item.get("bookOrReportDetails"), dict) else item.get("title")
                rows.append(
                    {
                        "source": "europepmc",
                        "id": item.get("id") or item.get("pmid") or item.get("doi"),
                        "title": _clip(title, 220),
                        "authors": _clip(item.get("authorString"), 180),
                        "journal": item.get("journalTitle") or item.get("pubType"),
                        "year": item.get("pubYear"),
                        "doi": item.get("doi"),
                        "url": item.get("fullTextUrl") or item.get("pmcid") or item.get("doi"),
                    }
                )

    if source_norm in {"both", "arxiv"}:
        resp, err = _parity.request(
            "GET",
            "https://export.arxiv.org/api/query",
            params={
                "search_query": f"all:{q}",
                "start": 0,
                "max_results": limit,
            },
            timeout=20,
            retries=2,
            raise_for_status=False,
        )
        if err is None and resp is not None and int(resp.status_code) == 200:
            try:
                root = ET.fromstring(resp.text)
                ns = {"a": "http://www.w3.org/2005/Atom"}
                for entry in root.findall("a:entry", ns):
                    title = (entry.findtext("a:title", default="", namespaces=ns) or "").strip()
                    published = (entry.findtext("a:published", default="", namespaces=ns) or "")
                    authors = [a.findtext("a:name", default="", namespaces=ns) for a in entry.findall("a:author", ns)]
                    rows.append(
                        {
                            "source": "arxiv",
                            "id": (entry.findtext("a:id", default="", namespaces=ns) or "").strip(),
                            "title": _clip(title, 220),
                            "authors": _clip(", ".join([a for a in authors if a]), 180),
                            "journal": "arXiv",
                            "year": published[:4] if published else None,
                            "doi": None,
                            "url": (entry.findtext("a:id", default="", namespaces=ns) or "").strip(),
                        }
                    )
            except Exception:
                pass

    # Deduplicate by title/url
    seen = set()
    deduped = []
    for row in rows:
        key = (row.get("title"), row.get("url"))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)

    deduped = deduped[:limit]
    return {
        "summary": f"Found {len(deduped)} preprints for '{q}'.",
        "query": q,
        "source": source_norm,
        "articles": deduped,
        "count": len(deduped),
    }
