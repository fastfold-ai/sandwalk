"""
protein.domain_annotate: InterPro domain/family/site annotation.

Split from tools/protein.py.
"""

import re

from tools import registry
from tools.http_client import request


@registry.register(
    name="protein.domain_annotate",
    description="Annotate protein domains, families, and functional sites using InterPro",
    category="protein",
    parameters={
        "gene": "Gene symbol (e.g. TP53) or domain/family keyword (e.g. CAP superfamily)",
        "uniprot_id": "UniProt accession (e.g. P04637) — used directly if provided",
    },
    usage_guide="You need detailed domain architecture for a protein — domain boundaries, family classifications, active sites, binding sites. Can also search InterPro by domain/family keyword when no UniProt accession can be resolved.",
)
def domain_annotate(gene: str = None, uniprot_id: str = None, **kwargs) -> dict:
    """Annotate domains using InterPro API.

    Resolves gene to UniProt ID if needed, then queries InterPro for full
    domain architecture including Pfam, SMART, PROSITE, and other member databases.
    """
    if not gene and not uniprot_id:
        return {
            "error": "Provide either gene symbol or uniprot_id",
            "summary": "No gene or UniProt ID specified",
        }

    non_human_hints = (
        "helminth", "parasite", "schistosoma", "fasciola", "heligmosomoides",
        "nematode", "trematode", "cestode", "worm", "brugia", "filaria",
    )

    def _looks_non_human(text: str) -> bool:
        t = (text or "").lower()
        return any(h in t for h in non_human_hints)

    def _resolve_uniprot(gene_query: str) -> tuple[str, list[str]]:
        attempts: list[str] = []
        search_terms: list[str] = []
        if _looks_non_human(gene_query):
            search_terms.extend([gene_query, f"{gene_query} AND reviewed:true"])
        else:
            search_terms.extend(
                [
                    f"{gene_query} AND organism_id:9606",
                    gene_query,
                ]
            )

        for term in search_terms:
            if term in attempts:
                continue
            attempts.append(term)
            resp, error = request(
                "GET",
                "https://rest.uniprot.org/uniprotkb/search",
                params={
                    "query": term,
                    "format": "json",
                    "size": "1",
                    "fields": "accession,gene_names",
                },
                timeout=15,
                headers={"Accept": "application/json"},
                raise_for_status=False,
            )
            if error or resp.status_code != 200:
                continue
            try:
                results = resp.json().get("results", [])
            except Exception:
                results = []
            if results:
                accession = results[0].get("primaryAccession", "")
                if accession:
                    return accession, attempts
        return "", attempts

    def _interpro_keyword_search(term: str) -> dict | None:
        cleaned = " ".join((term or "").split())
        if not cleaned:
            return None

        endpoints = (
            "https://www.ebi.ac.uk/interpro/api/entry/interpro/",
            "https://www.ebi.ac.uk/interpro/api/entry/all/",
        )
        for endpoint in endpoints:
            resp, error = request(
                "GET",
                endpoint,
                params={"search": cleaned, "page_size": "20"},
                timeout=15,
                headers={"Accept": "application/json"},
                raise_for_status=False,
            )
            if error or resp.status_code != 200:
                continue
            try:
                data = resp.json()
            except Exception:
                continue
            results = data.get("results", [])
            if not results:
                continue

            domains = []
            families = []
            for entry in results:
                md = entry.get("metadata", {}) or {}
                etype = md.get("type", "")
                annotation = {
                    "accession": md.get("accession", ""),
                    "name": md.get("name", ""),
                    "type": etype,
                    "source_database": md.get("source_database", ""),
                    "description": (
                        (md.get("description") or [{}])[0].get("text", "")
                        if isinstance(md.get("description"), list)
                        else ""
                    )[:200],
                    "locations": [],
                }
                if etype == "domain":
                    domains.append(annotation)
                elif etype == "family":
                    families.append(annotation)

            return {
                "summary": (
                    f"InterPro keyword search '{cleaned}': "
                    f"{len(domains)} domains, {len(families)} families (no single UniProt mapping)."
                ),
                "gene": gene,
                "uniprot_id": None,
                "n_domains": len(domains),
                "n_families": len(families),
                "n_sites": 0,
                "domains": domains[:30],
                "families": families[:30],
                "sites": [],
                "homologous_superfamilies": [],
                "total_annotations": len(results),
                "mode": "interpro_keyword_search",
            }
        return None

    # InterPro entry accession mode (e.g. IPR014044) for domain-family lookup.
    interpro_accession = None
    if isinstance(uniprot_id, str) and re.fullmatch(r"IPR\d{6,}", uniprot_id.strip().upper() or ""):
        interpro_accession = uniprot_id.strip().upper()
    elif isinstance(gene, str) and re.fullmatch(r"IPR\d{6,}", gene.strip().upper() or ""):
        interpro_accession = gene.strip().upper()

    if interpro_accession:
        resp, error = request(
            "GET",
            f"https://www.ebi.ac.uk/interpro/api/entry/interpro/{interpro_accession}",
            timeout=15,
            headers={"Accept": "application/json"},
            raise_for_status=False,
        )
        if error or resp.status_code != 200:
            # Fallback through keyword search path
            keyword_result = _interpro_keyword_search(interpro_accession)
            if keyword_result is not None:
                return keyword_result
            return {
                "error": f"InterPro entry lookup failed for {interpro_accession}",
                "summary": f"No InterPro entry found for {interpro_accession}",
            }

        try:
            data = resp.json()
        except Exception:
            return {
                "error": f"Invalid InterPro response for {interpro_accession}",
                "summary": f"Failed to parse InterPro response for {interpro_accession}",
            }
        results = data.get("results", [])
        if not results:
            return {
                "error": f"No InterPro entry results for {interpro_accession}",
                "summary": f"No InterPro data for {interpro_accession}",
            }

        domains = []
        families = []
        for entry in results:
            md = entry.get("metadata", {}) or {}
            etype = md.get("type", "")
            annotation = {
                "accession": md.get("accession", ""),
                "name": md.get("name", ""),
                "type": etype,
                "source_database": md.get("source_database", ""),
                "description": (
                    (md.get("description") or [{}])[0].get("text", "")
                    if isinstance(md.get("description"), list)
                    else ""
                )[:200],
                "locations": [],
            }
            if etype == "domain":
                domains.append(annotation)
            elif etype == "family":
                families.append(annotation)
        return {
            "summary": (
                f"InterPro {interpro_accession}: {len(domains)} domains, {len(families)} families."
            ),
            "gene": gene,
            "uniprot_id": None,
            "n_domains": len(domains),
            "n_families": len(families),
            "n_sites": 0,
            "domains": domains,
            "families": families,
            "sites": [],
            "homologous_superfamilies": [],
            "total_annotations": len(results),
            "mode": "interpro_accession_lookup",
        }

    # Resolve gene to UniProt ID if needed
    if not uniprot_id and gene:
        uniprot_id, attempts = _resolve_uniprot(gene)

        if not uniprot_id:
            keyword_result = _interpro_keyword_search(gene)
            if keyword_result is not None:
                return keyword_result
            attempted = "; ".join(attempts[:4])
            return {
                "error": f"Could not resolve gene {gene} to UniProt ID",
                "summary": f"Gene {gene} not found in UniProt search",
                "resolution_attempts": attempts,
                "attempted_query_preview": attempted,
            }

    # Query InterPro for protein domain annotations
    resp, error = request(
        "GET",
        f"https://www.ebi.ac.uk/interpro/api/entry/all/protein/uniprot/{uniprot_id}",
        timeout=15,
        headers={"Accept": "application/json"},
        raise_for_status=False,
    )
    if error:
        # Final fallback: keyword search if a gene/domain term is available.
        if gene:
            keyword_result = _interpro_keyword_search(gene)
            if keyword_result is not None:
                return keyword_result
        return {"error": f"InterPro API error: {error}", "summary": f"Failed to query InterPro for {uniprot_id}"}
    if resp.status_code == 204:
        data = {"results": []}
    elif resp.status_code != 200:
        if gene:
            keyword_result = _interpro_keyword_search(gene)
            if keyword_result is not None:
                return keyword_result
        return {
            "error": f"InterPro query failed for {uniprot_id} (HTTP {resp.status_code})",
            "summary": f"No InterPro data for {uniprot_id}",
        }
    else:
        try:
            data = resp.json()
        except Exception:
            return {"error": f"Invalid InterPro response for {uniprot_id}", "summary": f"Failed to parse InterPro response for {uniprot_id}"}

    # Parse InterPro results
    entries = data.get("results", [])

    domains = []
    families = []
    sites = []
    homologous_superfamilies = []

    for entry in entries:
        metadata = entry.get("metadata", {})
        entry_type = metadata.get("type", "")
        entry_name = metadata.get("name", "")
        entry_accession = metadata.get("accession", "")
        source_db = metadata.get("source_database", "")
        description = metadata.get("description", [])
        desc_text = description[0].get("text", "") if description else ""

        # Get protein locations (domain positions)
        proteins = entry.get("proteins", [])
        locations = []
        for protein in proteins:
            for loc_group in protein.get("entry_protein_locations", []):
                for fragment in loc_group.get("fragments", []):
                    locations.append({
                        "start": fragment.get("start"),
                        "end": fragment.get("end"),
                    })

        annotation = {
            "accession": entry_accession,
            "name": entry_name,
            "type": entry_type,
            "source_database": source_db,
            "description": desc_text[:200],
            "locations": locations,
        }

        if entry_type == "domain":
            domains.append(annotation)
        elif entry_type == "family":
            families.append(annotation)
        elif entry_type in ("active_site", "binding_site", "conserved_site", "ptm"):
            sites.append(annotation)
        elif entry_type == "homologous_superfamily":
            homologous_superfamilies.append(annotation)

    # Build summary
    gene_label = gene or uniprot_id
    domain_strs = []
    for d in domains:
        loc_str = ""
        if d["locations"]:
            locs = d["locations"][0]
            loc_str = f" ({locs['start']}-{locs['end']})"
        domain_strs.append(f"{d['name']}{loc_str}")

    summary = (
        f"{gene_label}: {len(domains)} domain{'s' if len(domains) != 1 else ''}"
    )
    if domain_strs:
        summary += f" — {', '.join(domain_strs[:6])}"

    return {
        "summary": summary,
        "gene": gene,
        "uniprot_id": uniprot_id,
        "n_domains": len(domains),
        "n_families": len(families),
        "n_sites": len(sites),
        "domains": domains,
        "families": families,
        "sites": sites,
        "homologous_superfamilies": homologous_superfamilies,
        "total_annotations": len(entries),
    }
