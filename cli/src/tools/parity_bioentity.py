"""parity: MyGene/MyDisease/MyVariant/MyTaxon/MyChem lookup tools.

Split from tools/parity.py. Calls ``request_json`` indirectly via the
``tools.parity`` hub module so that ``patch("tools.parity.request_json")``
in tests continues to work regardless of which submodule performs the call.
"""

from __future__ import annotations

from tools import parity as _parity
from tools import registry
from tools.parity_common import _coerce_int, _flatten_hits, _normalize_mygene_species


@registry.register(
    name="data_api.mygene_lookup",
    description="Lookup genes via MyGene.info",
    category="data_api",
    parameters={
        "query": "Gene symbol/name/identifier (e.g., TP53, ENSG00000141510)",
        "species": "Species filter (default human)",
        "size": "Maximum hits (default 10)",
    },
    usage_guide="Use for rapid gene identifier normalization and annotation via MyGene.info.",
)
def mygene_lookup(query: str, species: str = "human", size: int = 10, **kwargs) -> dict:
    """Query MyGene.info for gene-level metadata."""
    q = (query or "").strip()
    if not q:
        return {"summary": "query is required.", "error": "missing_query"}

    species_norm = _normalize_mygene_species(species)

    data, error = _parity.request_json(
        "GET",
        "https://mygene.info/v3/query",
        params={
            "q": q,
            "species": species_norm,
            "size": _coerce_int(size, 10),
            "fields": "symbol,name,entrezgene,ensembl.gene,taxid,type_of_gene",
        },
        timeout=20,
        retries=2,
    )
    if error:
        return {"summary": f"MyGene lookup failed: {error}", "error": "api_error"}

    hits = _flatten_hits(data)
    rows = []
    for hit in hits:
        ens = hit.get("ensembl")
        if isinstance(ens, list) and ens:
            ensembl_gene = ens[0].get("gene")
        elif isinstance(ens, dict):
            ensembl_gene = ens.get("gene")
        else:
            ensembl_gene = None
        rows.append(
            {
                "symbol": hit.get("symbol"),
                "name": hit.get("name"),
                "entrezgene": hit.get("entrezgene"),
                "ensembl_gene": ensembl_gene,
                "taxid": hit.get("taxid"),
                "type_of_gene": hit.get("type_of_gene"),
                "score": hit.get("_score"),
            }
        )

    return {
        "summary": f"MyGene: found {len(rows)} hits for '{q}'.",
        "query": q,
        "species": species_norm,
        "requested_species": species,
        "hits": rows,
        "count": len(rows),
        "source": "mygene.info",
    }


@registry.register(
    name="data_api.mydisease_lookup",
    description="Lookup diseases via MyDisease.info",
    category="data_api",
    parameters={
        "query": "Disease keyword/identifier",
        "size": "Maximum hits (default 10)",
    },
    usage_guide="Use for disease identifier mapping and cross-source disease metadata.",
)
def mydisease_lookup(query: str, size: int = 10, **kwargs) -> dict:
    """Query MyDisease.info for disease metadata."""
    q = (query or "").strip()
    if not q:
        return {"summary": "query is required.", "error": "missing_query"}

    data, error = _parity.request_json(
        "GET",
        "https://mydisease.info/v1/query",
        params={"q": q, "size": _coerce_int(size, 10)},
        timeout=20,
        retries=2,
    )
    if error:
        return {"summary": f"MyDisease lookup failed: {error}", "error": "api_error"}

    rows = []
    for hit in _flatten_hits(data):
        disease_name = hit.get("name")
        doid = None
        do_block = hit.get("disease_ontology")
        if isinstance(do_block, dict):
            doid = do_block.get("doid") or do_block.get("id")
            disease_name = disease_name or do_block.get("name")
        rows.append(
            {
                "name": disease_name,
                "doid": doid,
                "mondo": hit.get("mondo"),
                "score": hit.get("_score"),
                "id": hit.get("_id"),
            }
        )

    return {
        "summary": f"MyDisease: found {len(rows)} hits for '{q}'.",
        "query": q,
        "hits": rows,
        "count": len(rows),
        "source": "mydisease.info",
    }


@registry.register(
    name="data_api.myvariant_lookup",
    description="Lookup variants via MyVariant.info",
    category="data_api",
    parameters={
        "query": "Variant keyword/identifier (e.g., rs121913529, chr17:g.7673803G>A)",
        "size": "Maximum hits (default 10)",
    },
    usage_guide="Use for quick variant annotation triage from aggregated public sources.",
)
def myvariant_lookup(query: str, size: int = 10, **kwargs) -> dict:
    """Query MyVariant.info for variant annotations."""
    q = (query or "").strip()
    if not q:
        return {"summary": "query is required.", "error": "missing_query"}

    data, error = _parity.request_json(
        "GET",
        "https://myvariant.info/v1/query",
        params={
            "q": q,
            "size": _coerce_int(size, 10),
            "fields": "dbsnp.rsid,clinvar.hgvs,clinvar.clinsig,vcf.gene,vcf.position",
        },
        timeout=20,
        retries=2,
    )
    if error:
        return {"summary": f"MyVariant lookup failed: {error}", "error": "api_error"}

    rows = []
    for hit in _flatten_hits(data):
        dbsnp = hit.get("dbsnp")
        rsid = None
        if isinstance(dbsnp, dict):
            rsid = dbsnp.get("rsid")
        clinvar = hit.get("clinvar") if isinstance(hit.get("clinvar"), dict) else {}
        vcf = hit.get("vcf") if isinstance(hit.get("vcf"), dict) else {}
        rows.append(
            {
                "id": hit.get("_id"),
                "rsid": rsid,
                "hgvs": clinvar.get("hgvs"),
                "clinical_significance": clinvar.get("clinsig"),
                "gene": vcf.get("gene"),
                "position": vcf.get("position"),
                "score": hit.get("_score"),
            }
        )

    return {
        "summary": f"MyVariant: found {len(rows)} hits for '{q}'.",
        "query": q,
        "hits": rows,
        "count": len(rows),
        "source": "myvariant.info",
    }


@registry.register(
    name="data_api.mytaxon_lookup",
    description="Lookup taxonomy records via MyTaxon.info",
    category="data_api",
    parameters={
        "query": "Species/taxon keyword or taxonomy ID",
        "size": "Maximum hits (default 10)",
    },
    usage_guide="Use for organism/taxonomy normalization in multi-species analyses.",
)
def mytaxon_lookup(query: str, size: int = 10, **kwargs) -> dict:
    """Query MyTaxon.info for taxonomy metadata."""
    q = (query or "").strip()
    if not q:
        return {"summary": "query is required.", "error": "missing_query"}

    data, error = _parity.request_json(
        "GET",
        "https://mytaxon.info/v1/query",
        params={"q": q, "size": _coerce_int(size, 10)},
        timeout=20,
        retries=2,
    )
    if error:
        return {"summary": f"MyTaxon lookup failed: {error}", "error": "api_error"}

    rows = []
    for hit in _flatten_hits(data):
        rows.append(
            {
                "taxid": hit.get("_id") or hit.get("taxid"),
                "scientific_name": hit.get("scientific_name"),
                "common_name": hit.get("common_name"),
                "rank": hit.get("rank"),
                "parent_taxid": hit.get("parent_taxid"),
                "score": hit.get("_score"),
            }
        )

    return {
        "summary": f"MyTaxon: found {len(rows)} hits for '{q}'.",
        "query": q,
        "hits": rows,
        "count": len(rows),
        "source": "mytaxon.info",
    }


@registry.register(
    name="data_api.mychem_lookup",
    description="Lookup compounds/drugs via MyChem.info",
    category="data_api",
    parameters={
        "query": "Compound/drug keyword or identifier",
        "size": "Maximum hits (default 10)",
    },
    usage_guide="Use for rapid integrated compound metadata lookup across public sources.",
)
def mychem_lookup(query: str, size: int = 10, **kwargs) -> dict:
    """Query MyChem.info for compound metadata."""
    q = (query or "").strip()
    if not q:
        return {"summary": "query is required.", "error": "missing_query"}

    data, error = _parity.request_json(
        "GET",
        "https://mychem.info/v1/query",
        params={"q": q, "size": _coerce_int(size, 10)},
        timeout=20,
        retries=2,
    )
    if error:
        return {"summary": f"MyChem lookup failed: {error}", "error": "api_error"}

    rows = []
    for hit in _flatten_hits(data):
        chembl = hit.get("chembl") if isinstance(hit.get("chembl"), dict) else {}
        drugbank = hit.get("drugbank") if isinstance(hit.get("drugbank"), dict) else {}
        rows.append(
            {
                "id": hit.get("_id"),
                "name": hit.get("name") or hit.get("pref_name") or chembl.get("pref_name"),
                "chembl_id": chembl.get("molecule_chembl_id"),
                "drugbank_id": drugbank.get("id"),
                "inchi_key": hit.get("inchi_key"),
                "smiles": hit.get("smiles") or chembl.get("molecule_structures", {}).get("canonical_smiles") if isinstance(chembl.get("molecule_structures"), dict) else None,
                "score": hit.get("_score"),
            }
        )

    return {
        "summary": f"MyChem: found {len(rows)} hits for '{q}'.",
        "query": q,
        "hits": rows,
        "count": len(rows),
        "source": "mychem.info",
    }
