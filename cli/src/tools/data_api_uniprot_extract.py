"""data_api.uniprot_lookup: field extraction from a resolved UniProt entry. Split from tools/data_api.py."""


def extract_fields(entry: dict, query: str, org_clause: str | None, matched_query: str | None) -> dict:
    accession = entry.get("primaryAccession", "")
    gene_names = []
    for g in entry.get("genes", []):
        gn = g.get("geneName", {}).get("value")
        if gn:
            gene_names.append(gn)
        for syn in g.get("synonyms", []):
            gene_names.append(syn.get("value", ""))

    protein_name = (
        entry.get("proteinDescription", {}).get("recommendedName", {}).get("fullName", {}).get("value", "Unknown")
    )

    seq_info = entry.get("sequence", {})
    seq_length = seq_info.get("length", 0)

    function_texts = []
    subcellular = []
    tissue_specificity = ""
    diseases = []
    for c in entry.get("comments", []):
        comment_type = c.get("commentType")
        if comment_type == "FUNCTION":
            for t in c.get("texts", []):
                function_texts.append(t.get("value", ""))
        elif comment_type == "SUBCELLULAR LOCATION":
            for sl in c.get("subcellularLocations", []):
                loc = sl.get("location", {}).get("value", "")
                if loc:
                    subcellular.append(loc)
        elif comment_type == "TISSUE SPECIFICITY":
            for t in c.get("texts", []):
                tissue_specificity = t.get("value", "")
        elif comment_type == "DISEASE":
            disease = c.get("disease", {})
            if disease:
                diseases.append({
                    "name": disease.get("diseaseId", ""),
                    "description": disease.get("description", ""),
                    "acronym": disease.get("acronym", ""),
                })

    features = entry.get("features", [])
    domains = [
        {"name": f.get("description", ""), "type": f.get("type", "")}
        for f in features
        if f.get("type") in ("Domain", "Repeat", "Zinc finger", "Motif")
    ]

    xrefs = entry.get("uniProtKBCrossReferences", [])
    go_terms = []
    pdb_ids = []
    for xref in xrefs:
        db = xref.get("database", "")
        if db == "GO":
            props = {p["key"]: p["value"] for p in xref.get("properties", [])}
            go_terms.append({"id": xref.get("id", ""), "term": props.get("GoTerm", ""), "evidence": props.get("GoEvidenceType", "")})
        elif db == "PDB":
            pdb_ids.append(xref.get("id", ""))

    keywords = [kw.get("name", "") for kw in entry.get("keywords", [])]
    primary_gene = gene_names[0] if gene_names else query
    n_pdb = len(pdb_ids)

    return {
        "summary": (
            f"UniProt {accession} ({primary_gene}): {protein_name}, "
            f"{seq_length} aa. "
            + (f"{function_texts[0][:120]}... " if function_texts else "")
            + f"{n_pdb} PDB structure(s)."
        ),
        "matched_query": matched_query if matched_query is not None else query,
        "organism_filter": org_clause or "none",
        "accession": accession,
        "gene_names": gene_names,
        "protein_name": protein_name,
        "sequence_length": seq_length,
        "function": function_texts,
        "subcellular_location": subcellular,
        "tissue_specificity": tissue_specificity,
        "diseases": diseases[:10],
        "domains": domains[:20],
        "go_terms": go_terms[:30],
        "pdb_ids": pdb_ids[:30],
        "n_pdb_structures": n_pdb,
        "keywords": keywords,
        "uniprot_url": f"https://www.uniprot.org/uniprot/{accession}",
    }
