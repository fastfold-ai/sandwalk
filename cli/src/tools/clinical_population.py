"""clinical.indication_map / population_size: PRISM-derived epidemiology and market sizing.

Split from tools/clinical.py.

References crews-glue-discovery/scripts/patient_population_sizing.py for data sources
and scoring logic.
"""

import pandas as pd

from tools import registry

# US annual incidence by cancer type (SEER/Globocan estimates)
US_INCIDENCE = {
    "Lung": 238000,
    "Breast": 310000,
    "Colorectal": 153000,
    "Prostate": 288000,
    "Lymphoma (NHL)": 80000,
    "AML": 20000,
    "ALL": 6000,
    "Multiple Myeloma": 35000,
    "Kidney": 82000,
    "Liver": 42000,
    "Ovarian": 20000,
    "Pancreatic": 64000,
    "Melanoma": 100000,
    "Bladder": 83000,
    "Thyroid": 44000,
    "Glioma/Brain": 25000,
    "Cervical": 14000,
    "Endometrial/Uterine": 66000,
    "Head & Neck": 66000,
    "Gastric/Esophageal": 49000,
    "Sarcoma": 14000,
    "Neuroblastoma": 800,
    "Mesothelioma": 3000,
}

# PRISM lineage to standard cancer type mapping
LINEAGE_TO_CANCER = {
    "Lung": {"incidence_key": "Lung", "fraction": 0.85, "five_yr_survival": 0.25,
             "unmet_need": True, "name": "Non-Small Cell Lung Cancer"},
    "CNS/Brain": {"incidence_key": "Glioma/Brain", "fraction": 0.60, "five_yr_survival": 0.05,
                  "unmet_need": True, "name": "Diffuse Glioma"},
    "Skin": {"incidence_key": "Melanoma", "fraction": 1.0, "five_yr_survival": 0.93,
             "unmet_need": False, "name": "Melanoma"},
    "Lymphoid": {"incidence_key": "Lymphoma (NHL)", "fraction": 0.85, "five_yr_survival": 0.73,
                 "unmet_need": False, "name": "B-Cell Lymphoma"},
    "Head and Neck": {"incidence_key": "Head & Neck", "fraction": 0.90, "five_yr_survival": 0.66,
                      "unmet_need": False, "name": "Head & Neck SCC"},
    "Bowel": {"incidence_key": "Colorectal", "fraction": 0.95, "five_yr_survival": 0.65,
              "unmet_need": False, "name": "Colorectal Cancer"},
    "Ovary/Fallopian Tube": {"incidence_key": "Ovarian", "fraction": 0.90, "five_yr_survival": 0.50,
                             "unmet_need": True, "name": "Ovarian Cancer"},
    "Pancreas": {"incidence_key": "Pancreatic", "fraction": 0.85, "five_yr_survival": 0.12,
                 "unmet_need": True, "name": "Pancreatic Cancer"},
    "Breast": {"incidence_key": "Breast", "fraction": 0.95, "five_yr_survival": 0.90,
               "unmet_need": False, "name": "Breast Cancer"},
    "Prostate": {"incidence_key": "Prostate", "fraction": 0.95, "five_yr_survival": 0.97,
                 "unmet_need": False, "name": "Prostate Cancer"},
    "Myeloid": {"incidence_key": "AML", "fraction": 1.0, "five_yr_survival": 0.30,
                "unmet_need": True, "name": "Acute Myeloid Leukemia"},
    "Liver": {"incidence_key": "Liver", "fraction": 0.80, "five_yr_survival": 0.20,
              "unmet_need": True, "name": "Hepatocellular Carcinoma"},
    "Kidney": {"incidence_key": "Kidney", "fraction": 0.85, "five_yr_survival": 0.77,
               "unmet_need": False, "name": "Renal Cell Carcinoma"},
    "Bladder/Urinary Tract": {"incidence_key": "Bladder", "fraction": 0.90, "five_yr_survival": 0.77,
                              "unmet_need": False, "name": "Bladder Cancer"},
    "Stomach": {"incidence_key": "Gastric/Esophageal", "fraction": 0.65, "five_yr_survival": 0.22,
                "unmet_need": True, "name": "Gastric/Esophageal Cancer"},
    "Uterus": {"incidence_key": "Endometrial/Uterine", "fraction": 0.90, "five_yr_survival": 0.81,
               "unmet_need": False, "name": "Endometrial Cancer"},
    "Cervix": {"incidence_key": "Cervical", "fraction": 0.70, "five_yr_survival": 0.66,
               "unmet_need": True, "name": "Cervical Cancer"},
    "Bone": {"incidence_key": "Sarcoma", "fraction": 0.11, "five_yr_survival": 0.60,
             "unmet_need": True, "name": "Bone Sarcoma"},
    "Soft Tissue": {"incidence_key": "Sarcoma", "fraction": 0.05, "five_yr_survival": 0.63,
                    "unmet_need": True, "name": "Soft Tissue Sarcoma"},
    "Pleura": {"incidence_key": "Mesothelioma", "fraction": 0.80, "five_yr_survival": 0.12,
               "unmet_need": True, "name": "Mesothelioma"},
}


@registry.register(
    name="clinical.indication_map",
    description="Map compound sensitivity profiles to cancer indications with response rates",
    category="clinical",
    parameters={
        "compound_id": "Compound ID to map (or 'all')",
        "min_response_rate": "Minimum response rate to include (default 0.1)",
    },
    requires_data=["prism", "depmap_model"],
    usage_guide="You want to know which cancer types a compound is active against. Maps PRISM cell line sensitivity to clinical cancer indications. Use for indication selection and clinical positioning.",
)
def indication_map(compound_id: str = "all", min_response_rate: float = 0.1, **kwargs) -> dict:
    """Map compound PRISM sensitivity to cancer indications.

    Uses cell line lineage annotations to group by cancer type and compute
    per-indication response rates (fraction of cell lines with LFC < -0.5).
    """
    from data.loaders import load_model_metadata, load_prism

    prism = load_prism()
    model = load_model_metadata()

    # Map cell lines to lineages
    ccle_to_lineage = {}
    for _, row in model.iterrows():
        ccle = row.get("CCLEName", "")
        lin = row.get("OncotreeLineage", "Unknown")
        if pd.notna(ccle) and pd.notna(lin):
            ccle_to_lineage[ccle] = lin

    compounds = [compound_id] if compound_id != "all" else prism["pert_name"].unique().tolist()
    results = []

    for cpd in compounds:
        cpd_data = prism[prism["pert_name"] == cpd]
        if len(cpd_data) == 0:
            continue

        max_dose = cpd_data["pert_dose"].max()
        cpd_hd = cpd_data[cpd_data["pert_dose"] == max_dose].copy()
        cpd_hd["lineage"] = cpd_hd["ccle_name"].map(ccle_to_lineage)

        for lineage, group in cpd_hd.groupby("lineage"):
            if lineage == "Unknown" or len(group) < 3:
                continue

            n_cells = len(group)
            n_sensitive = (group["LFC"] < -0.5).sum()
            response_rate = n_sensitive / n_cells
            mean_lfc = float(group["LFC"].mean())

            if response_rate < min_response_rate:
                continue

            # Map to clinical indication
            cancer_info = LINEAGE_TO_CANCER.get(lineage, {})
            cancer_name = cancer_info.get("name", lineage)

            results.append({
                "compound": cpd,
                "lineage": lineage,
                "cancer_type": cancer_name,
                "n_cell_lines": n_cells,
                "n_sensitive": int(n_sensitive),
                "response_rate": round(response_rate, 3),
                "mean_lfc": round(mean_lfc, 3),
                "unmet_need": cancer_info.get("unmet_need"),
                "five_yr_survival": cancer_info.get("five_yr_survival"),
            })

    if not results:
        return {
            "summary": f"No indications found for {compound_id} (compound may not be in PRISM data or no lineages met criteria)",
            "n_indications": 0,
            "indications": [],
        }

    df = pd.DataFrame(results).sort_values("response_rate", ascending=False)

    if compound_id != "all":
        top = df.head(5)
        top_names = ", ".join(top["cancer_type"].tolist()) if len(top) > 0 else "none"
        summary = f"Indication mapping for {compound_id}: {len(df)} indications (top: {top_names})"
    else:
        summary = f"Mapped {len(compounds)} compounds across {df['cancer_type'].nunique()} indications"

    return {
        "summary": summary,
        "n_indications": len(df),
        "indications": df.to_dict("records"),
    }


@registry.register(
    name="clinical.population_size",
    description="Estimate addressable patient population per compound and indication using SEER incidence data",
    category="clinical",
    parameters={
        "compound_id": "Compound ID to size (or 'all')",
        "clinical_adjustment": "Clinical reality factor (default 0.10 = 10% of cell-line estimate)",
    },
    requires_data=["prism", "depmap_model"],
    usage_guide="You want to estimate how many patients could benefit from a compound — combines PRISM response rates with US cancer incidence data. Use for market sizing and clinical development prioritization.",
)
def population_size(compound_id: str = "all", clinical_adjustment: float = 0.10, **kwargs) -> dict:
    """Estimate addressable patient populations.

    addressable = annual_incidence x subtype_fraction x cell_line_response_rate
    clinical_adjusted = addressable x clinical_adjustment_factor
    """
    # Get indication mapping first
    ind_result = indication_map(compound_id=compound_id, min_response_rate=0.05)
    if "error" in ind_result:
        return ind_result

    indications = ind_result["indications"]
    results = []

    for ind in indications:
        lineage = ind["lineage"]
        cancer_info = LINEAGE_TO_CANCER.get(lineage)
        if not cancer_info:
            continue

        incidence_key = cancer_info["incidence_key"]
        if incidence_key not in US_INCIDENCE:
            continue

        annual_incidence = US_INCIDENCE[incidence_key]
        subtype_fraction = cancer_info["fraction"]
        base_population = int(annual_incidence * subtype_fraction)
        addressable = int(base_population * ind["response_rate"])
        clinical_est = int(addressable * clinical_adjustment)

        results.append({
            "compound": ind["compound"],
            "cancer_type": ind["cancer_type"],
            "annual_us_incidence": annual_incidence,
            "subtype_fraction": subtype_fraction,
            "base_population": base_population,
            "response_rate": ind["response_rate"],
            "addressable_patients": addressable,
            "clinical_adjusted": clinical_est,
            "mean_lfc": ind["mean_lfc"],
            "n_cell_lines": ind["n_cell_lines"],
            "unmet_need": ind.get("unmet_need"),
            "five_yr_survival": ind.get("five_yr_survival"),
        })

    if not results:
        return {
            "summary": f"No addressable populations identified for {compound_id} (compound may not be in PRISM data)",
            "clinical_adjustment": clinical_adjustment,
            "per_indication": [],
            "per_compound": {},
        }

    df = pd.DataFrame(results).sort_values("addressable_patients", ascending=False)

    # Per-compound totals
    if len(df) > 0:
        cpd_totals = df.groupby("compound").agg(
            total_addressable=("addressable_patients", "sum"),
            total_clinical=("clinical_adjusted", "sum"),
            n_indications=("cancer_type", "nunique"),
        ).sort_values("total_addressable", ascending=False)

        top_cpd = cpd_totals.index[0] if len(cpd_totals) > 0 else "N/A"
        total = int(cpd_totals.iloc[0]["total_addressable"]) if len(cpd_totals) > 0 else 0

        summary = (
            f"Patient population sizing ({clinical_adjustment:.0%} clinical adjustment):\n"
            f"Top compound: {top_cpd} ({total:,} addressable, "
            f"{int(total * clinical_adjustment):,} clinical estimate)"
        )
    else:
        summary = "No addressable populations identified"
        cpd_totals = pd.DataFrame()

    return {
        "summary": summary,
        "clinical_adjustment": clinical_adjustment,
        "per_indication": df.to_dict("records"),
        "per_compound": cpd_totals.to_dict("index") if len(cpd_totals) > 0 else {},
    }
