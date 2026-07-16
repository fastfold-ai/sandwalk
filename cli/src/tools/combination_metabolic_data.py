"""Metabolic pathway gene sets and known inhibitors for combination.metabolic_vulnerability."""

# Metabolic pathway gene sets (from metabolic_vulnerability.py)
METABOLIC_PATHWAYS = {
    "glycolysis": ["HK1", "HK2", "GPI", "PFKM", "PFKL", "ALDOA", "TPI1",
                   "GAPDH", "PGK1", "PGAM1", "ENO1", "ENO2", "PKM", "LDHA", "LDHB"],
    "oxidative_phosphorylation": ["NDUFA1", "NDUFA2", "NDUFB1", "NDUFS1", "SDHA", "SDHB",
                                  "UQCRC1", "UQCRC2", "COX5A", "COX5B", "ATP5F1A", "ATP5F1B"],
    "fatty_acid_synthesis": ["FASN", "ACACA", "ACLY", "SCD", "ELOVL1", "ELOVL5", "ELOVL6"],
    "fatty_acid_oxidation": ["CPT1A", "CPT1B", "CPT2", "ACADM", "ACADL", "ACADVL",
                             "HADHA", "HADHB", "ECHS1"],
    "glutamine_metabolism": ["GLS", "GLS2", "GLUD1", "SLC1A5", "SLC7A5", "GOT1", "GOT2"],
    "one_carbon_metabolism": ["MTHFR", "MTHFD1", "MTHFD2", "SHMT1", "SHMT2", "DHFR",
                              "TYMS", "MTR", "MAT2A"],
    "nucleotide_synthesis": ["CAD", "DHODH", "UMPS", "CTPS1", "CTPS2", "IMPDH1", "IMPDH2",
                             "PAICS", "ATIC", "GART"],
    "pentose_phosphate": ["G6PD", "PGLS", "PGD", "TKT", "TALDO1", "RPIA", "RPE"],
    "tca_cycle": ["CS", "ACO1", "ACO2", "IDH1", "IDH2", "IDH3A", "OGDH", "SUCLA2",
                  "SDHA", "FH", "MDH1", "MDH2"],
}

# Known metabolic inhibitors for combination suggestions
METABOLIC_INHIBITORS = {
    "glycolysis": ["2-DG (2-deoxyglucose)", "3-bromopyruvate", "lonidamine"],
    "oxidative_phosphorylation": ["metformin", "IACS-010759", "oligomycin A"],
    "fatty_acid_synthesis": ["TVB-2640 (denifanstat)", "orlistat", "TOFA"],
    "fatty_acid_oxidation": ["etomoxir", "ranolazine", "perhexiline"],
    "glutamine_metabolism": ["CB-839 (telaglenastat)", "BPTES", "DON"],
    "one_carbon_metabolism": ["methotrexate", "pemetrexed", "AG-270 (MAT2A inhibitor)"],
    "nucleotide_synthesis": ["brequinar (DHODH)", "mycophenolate (IMPDH)", "leflunomide"],
    "pentose_phosphate": ["6-AN (G6PD)", "DHEA (G6PD)", "oxythiamine (TKT)"],
    "tca_cycle": ["ivosidenib (IDH1)", "enasidenib (IDH2)", "CPI-613 (devimistat)"],
}
