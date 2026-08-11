"""safety: shared UniProt/gene mappings and anti-target gene sets. Split from tools/safety.py."""

# UniProt accession → gene symbol mapping for safety-relevant proteins.
# The proteomics matrix uses UniProt IDs as row index; all gene-symbol
# lookups must go through this mapping.
UNIPROT_TO_GENE = {
    # SALL family (teratogenicity)
    "Q9UJQ4": "SALL4", "Q9NSC2": "SALL1", "Q9Y467": "SALL2", "Q8N3A9": "SALL3",
    # IKZF family (heme TFs / CRBN substrates)
    "Q13422": "IKZF1", "Q9UKT9": "IKZF3", "Q9H2S1": "IKZF4",
    "Q96PU5": "IKZF2", "Q9H193": "IKZF5",
    # Other CRBN substrates
    "P15170": "GSPT1", "Q8IYD1": "GSPT2", "P48729": "CSNK1A1", "Q96SW2": "ZFP91",
    # Tumor suppressors
    "P04637": "TP53", "P06400": "RB1", "P60484": "PTEN", "P25054": "APC",
    "P38398": "BRCA1", "P51587": "BRCA2", "P40337": "VHL",
    "P21359": "NF1", "P35240": "NF2",
    "P42771": "CDKN2A", "P42772": "CDKN2B", "P19544": "WT1",
    "Q13315": "SMAD4", "Q15831": "STK11", "Q969H0": "FBXW7", "Q92560": "BAP1",
    "O14497": "ARID1A", "Q8NFD5": "ARID1B", "Q68CP9": "ARID2",
    "O14686": "KMT2D", "Q8NEZ4": "KMT2C", "Q9BYW2": "SETD2",
    "Q01196": "RUNX1", "Q13761": "RUNX3", "P23771": "GATA3",
    "P10914": "IRF1", "O15524": "SOCS1",
    # Heme TFs
    "P15976": "GATA1", "P23769": "GATA2", "P17542": "TAL1",
    "P17947": "SPI1", "P49715": "CEBPA", "P17676": "CEBPB",
    "P10242": "MYB", "P41212": "ETV6", "Q01543": "FLI1",
    # TP63 (teratogenic)
    "Q9H3D4": "TP63",
}
GENE_TO_UNIPROT = {v: k for k, v in UNIPROT_TO_GENE.items()}


def _gene_ids(gene_set, all_proteins):
    """Return the subset of protein IDs (UniProt or gene symbol) present in *all_proteins*
    that correspond to any gene in *gene_set*."""
    # Direct gene-symbol matches (in case the index already uses symbols)
    hits = gene_set & all_proteins
    # UniProt-ID matches
    for uid, gene in UNIPROT_TO_GENE.items():
        if gene in gene_set and uid in all_proteins:
            hits.add(uid)
    return hits


def _display_name(protein_id):
    """Return a human-readable name: 'GENE (UNIPROT)' when a mapping exists."""
    gene = UNIPROT_TO_GENE.get(protein_id)
    if gene:
        return f"{gene} ({protein_id})"
    return protein_id


# Known tumor suppressor genes (anti-targets for degradation)
TUMOR_SUPPRESSORS = {
    "TP53", "RB1", "PTEN", "APC", "BRCA1", "BRCA2", "VHL", "NF1", "NF2",
    "CDKN2A", "CDKN2B", "WT1", "SMAD4", "STK11", "FBXW7", "BAP1",
    "ARID1A", "ARID1B", "ARID2", "KMT2D", "KMT2C", "SETD2",
    "RUNX1", "RUNX3", "GATA3", "IRF1", "SOCS1",
}

# Essential hematopoietic transcription factors (high-risk degradation targets)
HEME_TFS = {
    "IKZF1", "IKZF3", "IKZF4", "GATA1", "GATA2", "TAL1", "RUNX1",
    "SPI1", "CEBPA", "CEBPB", "MYB", "ETV6", "FLI1",
}

# Known teratogenicity-associated CRBN substrates
TERATOGENIC_SUBSTRATES = {
    "SALL4", "SALL1", "SALL3",  # limb development TFs
    "p63", "TP63",  # epithelial development
}

# Known CRBN neosubstrates (degraded by IMiDs/molecular glues)
CRBN_SUBSTRATES = {
    "IKZF1", "IKZF3", "CK1A", "CSNK1A1", "GSPT1", "GSPT2",
    "ZFP91", "AIOLOS", "IKAROS",
}
