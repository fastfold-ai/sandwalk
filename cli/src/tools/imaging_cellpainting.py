"""Imaging tool: compound bioactivity profiling via PubChem assays and RDKit descriptors."""

from tools import registry
from tools.http_client import request


@registry.register(
    name="imaging.cellpainting_lookup",
    description="Look up compound bioactivity and compute mechanism class via PubChem assays and RDKit descriptors",
    category="imaging",
    parameters={
        "compound": "Compound name, InChIKey, or SMILES string",
        "source": "Data source: 'pubchem' (default). JUMP Cell Painting data requires local parquet files (not yet integrated).",
    },
    usage_guide="You want to understand a compound's bioactivity profile and infer its mechanism class. Queries PubChem bioassay data and computes RDKit molecular descriptors for heuristic mechanism classification. Note: full Cell Painting morphological profiles from JUMP require downloading parquet files from the JUMP Cell Painting Gallery (S3-hosted, no REST API).",
)
def cellpainting_lookup(compound: str, source: str = "pubchem", **kwargs) -> dict:
    """Look up compound bioactivity and mechanism class.

    Queries PubChem for bioassay data and computes RDKit molecular descriptors
    for heuristic mechanism classification. Full JUMP Cell Painting morphological
    profiles are not yet integrated (data is S3-hosted parquet, no REST API).
    """
    compound_info = {"query": compound, "source": source}

    # Step 1: Try to resolve compound via PubChem for identifiers
    cid = None
    canonical_smiles = None
    inchikey = None
    compound_name = compound

    # Check if input looks like SMILES (contains special chars)
    is_smiles = any(c in compound for c in "()=#/\\@[]")
    # Check if input looks like InChIKey (14-10-1 pattern)
    is_inchikey = len(compound) == 27 and compound.count("-") == 2

    if is_smiles:
        resp, error = request(
            "POST",
            "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/smiles/property/CID,CanonicalSMILES,InChIKey,IUPACName/JSON",
            data={"smiles": compound},
            timeout=10,
            raise_for_status=False,
        )
    elif is_inchikey:
        resp, error = request(
            "GET",
            f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/inchikey/{compound}/property/CID,CanonicalSMILES,InChIKey,IUPACName/JSON",
            timeout=10,
            raise_for_status=False,
        )
    else:
        import urllib.parse
        encoded = urllib.parse.quote(compound, safe="")
        resp, error = request(
            "GET",
            f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{encoded}/property/CID,CanonicalSMILES,InChIKey,IUPACName/JSON",
            timeout=10,
            raise_for_status=False,
        )

    if not error and resp.status_code == 200:
        try:
            props = resp.json().get("PropertyTable", {}).get("Properties", [])
        except Exception:
            props = []
        if props:
            cid = props[0].get("CID")
            canonical_smiles = props[0].get("CanonicalSMILES")
            inchikey = props[0].get("InChIKey")
            compound_name = props[0].get("IUPACName", compound)

    compound_info["cid"] = cid
    compound_info["canonical_smiles"] = canonical_smiles
    compound_info["inchikey"] = inchikey

    # Step 2: Search PubChem for bioactivity data
    mechanism_cluster = None
    bioactivity_data = []
    if cid:
        bio_resp, bio_error = request(
            "GET",
            f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{cid}/assaysummary/JSON",
            timeout=10,
            raise_for_status=False,
        )
        if not bio_error and bio_resp.status_code == 200:
            try:
                assays = bio_resp.json().get("Table", {}).get("Row", [])
            except Exception:
                assays = []
            # Filter for cell-based / imaging assays
            for row in assays[:50]:
                cells = row.get("Cell", [])
                # Each row is a dict with Cell entries
                if isinstance(cells, list) and len(cells) > 5:
                    aid = cells[0].get("StringValue", "") if isinstance(cells[0], dict) else str(cells[0])
                    activity = cells[3].get("StringValue", "") if len(cells) > 3 and isinstance(cells[3], dict) else ""
                    bioactivity_data.append({
                        "aid": aid,
                        "activity_outcome": activity,
                    })

    # Step 3: Compute molecular descriptors using RDKit if SMILES available
    rdkit_descriptors = None
    if canonical_smiles or is_smiles:
        try:
            from rdkit import Chem
            from rdkit.Chem import Descriptors, rdMolDescriptors

            smi = canonical_smiles or compound
            mol = Chem.MolFromSmiles(smi)
            if mol is not None:
                rdkit_descriptors = {
                    "molecular_weight": round(Descriptors.MolWt(mol), 2),
                    "logp": round(Descriptors.MolLogP(mol), 2),
                    "tpsa": round(Descriptors.TPSA(mol), 2),
                    "hba": Descriptors.NumHAcceptors(mol),
                    "hbd": Descriptors.NumHDonors(mol),
                    "rotatable_bonds": Descriptors.NumRotatableBonds(mol),
                    "aromatic_rings": Descriptors.NumAromaticRings(mol),
                    "fsp3": round(rdMolDescriptors.CalcFractionCSP3(mol), 3),
                }

                # Heuristic mechanism class based on molecular properties
                mw = rdkit_descriptors["molecular_weight"]
                logp = rdkit_descriptors["logp"]
                if mw < 500 and rdkit_descriptors["aromatic_rings"] >= 2:
                    mechanism_cluster = "kinase_inhibitor_like"
                elif mw < 600 and logp < 2:
                    mechanism_cluster = "protein_degrader_like"
                elif mw > 800:
                    mechanism_cluster = "macrocycle_like"
                else:
                    mechanism_cluster = "small_molecule"
        except ImportError:
            pass

    # Build summary
    has_data = bool(bioactivity_data or rdkit_descriptors)
    if has_data:
        cluster_str = f", mechanism cluster: '{mechanism_cluster}'" if mechanism_cluster else ""
        n_assays = len(bioactivity_data)
        assay_str = f", {n_assays} PubChem bioassay(s)" if n_assays > 0 else ""
        summary = (
            f"Compound profile for {compound}: "
            f"CID={cid or 'N/A'}{cluster_str}{assay_str}"
        )
    else:
        summary = (
            f"Compound profile for {compound}: no bioactivity data found in PubChem. "
            f"CID={cid or 'N/A'}"
        )

    result = {
        "summary": summary,
        "compound_info": compound_info,
        "compound_name": compound_name,
        "mechanism_cluster": mechanism_cluster,
        "bioactivity_assays": bioactivity_data[:20],
        "n_assays": len(bioactivity_data),
    }

    if rdkit_descriptors:
        result["molecular_descriptors"] = rdkit_descriptors

    return result
