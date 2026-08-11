"""data_api.ensembl_lookup: Ensembl REST gene lookup. Split from tools/data_api.py."""
from tools import data_api as _data_api
from tools import registry


@registry.register(
    name="data_api.ensembl_lookup",
    description="Look up gene information from Ensembl: genomic coordinates, transcripts, cross-references",
    category="data_api",
    parameters={
        "gene": "Gene symbol (e.g. BRCA1) or Ensembl ID (e.g. ENSG00000012048)",
        "species": "Species name (default 'human')",
    },
    requires_data=[],
    usage_guide="You need gene-level genomic information: Ensembl ID, chromosome location, transcripts, biotype, cross-references. Use for gene annotation and ID mapping.",
)
def ensembl_lookup(gene: str, species: str = "human", **kwargs) -> dict:
    """Look up gene information from the Ensembl REST API."""
    ensembl_base = "https://rest.ensembl.org"
    headers = {"Content-Type": "application/json", "Accept": "application/json"}

    species_map = {
        "human": "homo_sapiens", "mouse": "mus_musculus", "rat": "rattus_norvegicus",
        "zebrafish": "danio_rerio", "drosophila": "drosophila_melanogaster",
    }
    species_name = species_map.get(species.lower(), species.lower().replace(" ", "_"))

    gene_clean = gene.strip()

    # Determine if this is an Ensembl ID or a symbol
    if gene_clean.upper().startswith("ENSG") or gene_clean.upper().startswith("ENSMUSG"):
        # Direct ID lookup
        url = f"{ensembl_base}/lookup/id/{gene_clean}"
        params = {"expand": 1}
    else:
        # Symbol lookup
        url = f"{ensembl_base}/lookup/symbol/{species_name}/{gene_clean}"
        params = {"expand": 1}

    try:
        resp = _data_api._http_get(url, params=params, headers=headers, timeout=15, retries=2)
        if resp.status_code == 400:
            return {
                "error": f"Gene '{gene}' not found in Ensembl ({species})",
                "summary": f"Ensembl: gene '{gene}' not found for {species}",
            }
        if resp.status_code != 200:
            return {"error": f"Ensembl API returned HTTP {resp.status_code}", "summary": f"Ensembl API error: HTTP {resp.status_code}"}
        data = resp.json()
    except Exception as e:
        return {"error": f"Ensembl API error: {e}", "summary": f"Ensembl API error: {e}"}
    ensembl_id = data.get("id", "")
    display_name = data.get("display_name", gene)
    description = data.get("description", "")
    biotype = data.get("biotype", "")
    chromosome = data.get("seq_region_name", "")
    start = data.get("start")
    end = data.get("end")
    strand = data.get("strand")

    # Parse transcripts
    transcripts = []
    for t in data.get("Transcript", []):
        transcripts.append({
            "transcript_id": t.get("id", ""),
            "display_name": t.get("display_name", ""),
            "biotype": t.get("biotype", ""),
            "is_canonical": t.get("is_canonical", 0) == 1,
            "length": t.get("length"),
        })

    n_transcripts = len(transcripts)

    # Fetch cross-references (UniProt mapping)
    xrefs = []
    try:
        xref_resp = _data_api._http_get(
            f"{ensembl_base}/xrefs/id/{ensembl_id}",
            params={"external_db": "UniProt%"},
            headers=headers,
            timeout=10,
            retries=2,
        )
        if xref_resp.status_code == 200:
            for xref in xref_resp.json():
                xrefs.append({
                    "database": xref.get("dbname", ""),
                    "primary_id": xref.get("primary_id", ""),
                    "display_id": xref.get("display_id", ""),
                })
    except Exception:
        pass

    strand_str = "+" if strand == 1 else "-" if strand == -1 else "?"
    loc_str = f"chr{chromosome}:{start:,}-{end:,} ({strand_str})" if start and end else "unknown"

    return {
        "summary": (
            f"{display_name} ({ensembl_id}): {biotype}, "
            f"{loc_str}, {n_transcripts} transcripts"
        ),
        "ensembl_id": ensembl_id,
        "display_name": display_name,
        "description": description,
        "biotype": biotype,
        "chromosome": chromosome,
        "start": start,
        "end": end,
        "strand": strand,
        "location": loc_str,
        "n_transcripts": n_transcripts,
        "transcripts": transcripts[:20],
        "cross_references": xrefs[:10],
    }


# ---------------------------------------------------------------------------
# 6. NCBI Gene
# ---------------------------------------------------------------------------
