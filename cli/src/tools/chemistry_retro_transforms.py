"""chemistry.retrosynthesis: heuristic SMARTS disconnection transform library. Split from tools/chemistry.py."""

# Each transform: (name, product_smarts, reactant_smarts_list, reagents, conditions)
RETRO_TRANSFORMS = [
    {
        "name": "Amide bond disconnection",
        "description": "Disconnect C(=O)-N amide bond → carboxylic acid + amine",
        "product_smarts": "[C:1](=[O:2])-[N:3]",
        "reagents": ["HATU", "DIPEA"],
        "conditions": "Amide coupling, DMF, RT, 12h",
        "reaction_class": "amide_coupling",
    },
    {
        "name": "Suzuki coupling",
        "description": "Disconnect Ar-Ar biaryl bond → aryl boronic acid + aryl halide",
        "product_smarts": "[c:1]-[c:2]",
        "reagents": ["Pd(PPh3)4", "K2CO3"],
        "conditions": "Suzuki coupling, dioxane/H2O, 80°C, 16h",
        "reaction_class": "cross_coupling",
    },
    {
        "name": "Ester hydrolysis",
        "description": "Disconnect C(=O)-O ester bond → carboxylic acid + alcohol",
        "product_smarts": "[C:1](=[O:2])-[O:3][C:4]",
        "reagents": ["DCC", "DMAP"],
        "conditions": "Esterification, DCM, RT, 4h",
        "reaction_class": "esterification",
    },
    {
        "name": "Reductive amination",
        "description": "Disconnect C-N bond adjacent to C-H → aldehyde/ketone + amine",
        "product_smarts": "[C:1]-[NH:2]",
        "reagents": ["NaBH3CN", "AcOH"],
        "conditions": "Reductive amination, MeOH, RT, 16h",
        "reaction_class": "reductive_amination",
    },
    {
        "name": "N-alkylation",
        "description": "Disconnect N-C(sp3) bond → amine + alkyl halide",
        "product_smarts": "[N:1]-[CH2:2]",
        "reagents": ["K2CO3"],
        "conditions": "N-alkylation, DMF, 60°C, 12h",
        "reaction_class": "alkylation",
    },
    {
        "name": "Ether formation (Williamson)",
        "description": "Disconnect C-O-C ether bond → alcohol + alkyl halide",
        "product_smarts": "[C:1]-[O:2]-[C:3]",
        "reagents": ["NaH"],
        "conditions": "Williamson ether synthesis, THF, 0°C→RT, 6h",
        "reaction_class": "etherification",
    },
    {
        "name": "Sulfonamide formation",
        "description": "Disconnect S(=O)(=O)-N bond → sulfonyl chloride + amine",
        "product_smarts": "[S:1](=[O:2])(=[O:3])-[N:4]",
        "reagents": ["Et3N"],
        "conditions": "Sulfonamide coupling, DCM, 0°C→RT, 4h",
        "reaction_class": "sulfonamide_formation",
    },
    {
        "name": "Urea formation",
        "description": "Disconnect N-C(=O)-N urea → isocyanate + amine",
        "product_smarts": "[N:1]-[C:2](=[O:3])-[N:4]",
        "reagents": ["CDI or triphosgene"],
        "conditions": "Urea formation, DCM, RT, 12h",
        "reaction_class": "urea_formation",
    },
]
