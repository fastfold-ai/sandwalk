"""experiment.list_assays / design_assay / estimate_timeline tools.

Split from tools/experiment.py.
"""

from __future__ import annotations

import math

from tools import registry
from tools.experiment_templates import ASSAY_TEMPLATES


@registry.register(
    name="experiment.list_assays",
    description="List all available experimental assay templates with name, description, and category",
    category="experiment",
    parameters={},
    usage_guide="You want to see all available experimental assay types before designing a specific protocol.",
)
def list_assays(**kwargs) -> dict:
    """Return a catalogue of all available assay templates."""
    assays = []
    for key, tmpl in ASSAY_TEMPLATES.items():
        assays.append({
            "assay_type": key,
            "name": tmpl["name"],
            "description": tmpl["description"],
            "category": tmpl["category"],
        })

    by_category: dict[str, list[str]] = {}
    for a in assays:
        by_category.setdefault(a["category"], []).append(a["assay_type"])

    cat_summary = "; ".join(f"{cat}: {', '.join(types)}" for cat, types in sorted(by_category.items()))

    return {
        "summary": f"{len(assays)} assay templates available across {len(by_category)} categories. {cat_summary}",
        "assays": assays,
        "categories": by_category,
    }


@registry.register(
    name="experiment.design_assay",
    description="Design a detailed experimental protocol for a specific assay type, customized with target/compound/cell line information",
    category="experiment",
    parameters={
        "assay_type": "Assay template key (e.g. 'hibit', 'nanobret', 'tmt_proteomics')",
        "target": "Target protein or gene name",
        "compound": "Compound name or identifier",
        "cell_line": "Cell line to use",
        "goal": "Specific experimental goal or question",
    },
    usage_guide="You need to design an experimental protocol for validating a computational finding. Use before experiment.estimate_timeline and cro.match_experiment.",
)
def design_assay(
    assay_type: str,
    target: str = None,
    compound: str = None,
    cell_line: str = None,
    goal: str = None,
    **kwargs,
) -> dict:
    """Design a customized experimental protocol from a template."""
    if assay_type not in ASSAY_TEMPLATES:
        available = ", ".join(sorted(ASSAY_TEMPLATES.keys()))
        return {"error": f"Unknown assay type '{assay_type}'. Available: {available}", "summary": f"Unknown assay type '{assay_type}'. Available: {available}"}
    tmpl = ASSAY_TEMPLATES[assay_type]

    # Customize protocol steps with target/compound/cell_line info
    customized_steps = []
    for step in tmpl["protocol_steps"]:
        s = step
        if target:
            s = s.replace("target protein", f"{target} protein")
            s = s.replace("target gene", f"{target} gene")
        if compound:
            s = s.replace("compound", compound).replace("test compounds", compound)
        if cell_line:
            s = s.replace("cells", f"{cell_line} cells").replace("Plate cells", f"Plate {cell_line} cells")
        customized_steps.append(s)

    # Build customized controls
    controls = dict(tmpl["controls"])
    if target:
        controls["positive"] = controls["positive"].replace("target", target)
    if compound:
        controls["negative"] = controls["negative"].replace("compound", compound)

    # Build context string
    context_parts = []
    if target:
        context_parts.append(f"target={target}")
    if compound:
        context_parts.append(f"compound={compound}")
    if cell_line:
        context_parts.append(f"cell_line={cell_line}")
    if goal:
        context_parts.append(f"goal={goal}")
    context_str = ", ".join(context_parts) if context_parts else "generic protocol"

    # Assemble protocol
    protocol = {
        "assay_type": assay_type,
        "name": tmpl["name"],
        "description": tmpl["description"],
        "category": tmpl["category"],
        "context": context_str,
        "protocol_steps": customized_steps,
        "reagents": list(tmpl["reagents"]),
        "controls": controls,
        "readout": tmpl["readout"],
        "estimated_hands_on_hours": tmpl["hands_on_hours"],
        "estimated_calendar_days": tmpl["calendar_days"],
        "estimated_cost_per_plate": tmpl["cost_per_plate"],
    }

    if goal:
        protocol["experimental_goal"] = goal

    summary_parts = [f"Designed {tmpl['name']} protocol"]
    if target:
        summary_parts.append(f"for {target}")
    if compound:
        summary_parts.append(f"with {compound}")
    if cell_line:
        summary_parts.append(f"in {cell_line}")
    summary_parts.append(
        f"({len(customized_steps)} steps, ~{tmpl['hands_on_hours']}h hands-on, "
        f"{tmpl['calendar_days']} calendar days, ~${tmpl['cost_per_plate']}/plate)"
    )

    return {
        "summary": ". ".join(summary_parts),
        "protocol": protocol,
    }


@registry.register(
    name="experiment.estimate_timeline",
    description="Estimate hands-on time, calendar time, and cost for an experiment scaled by number of compounds, replicates, and doses",
    category="experiment",
    parameters={
        "assay_type": "Assay template key (e.g. 'hibit', 'ctg_viability')",
        "n_compounds": "Number of compounds to test",
        "n_replicates": "Number of biological replicates",
        "n_doses": "Number of dose points per compound",
    },
    usage_guide="You need to estimate how long an experiment will take and how much it will cost. Use after experiment.design_assay.",
)
def estimate_timeline(
    assay_type: str,
    n_compounds: int = 1,
    n_replicates: int = 3,
    n_doses: int = 8,
    **kwargs,
) -> dict:
    """Estimate timeline and cost scaled by experimental parameters."""
    if assay_type not in ASSAY_TEMPLATES:
        available = ", ".join(sorted(ASSAY_TEMPLATES.keys()))
        return {"error": f"Unknown assay type '{assay_type}'. Available: {available}", "summary": f"Unknown assay type '{assay_type}'. Available: {available}"}
    tmpl = ASSAY_TEMPLATES[assay_type]

    # Calculate number of wells needed
    # Each compound x dose x replicate = 1 well, plus controls (~10% overhead)
    wells_per_compound = n_doses * n_replicates
    total_wells = n_compounds * wells_per_compound
    control_wells = max(16, int(total_wells * 0.1))  # at least 16 control wells
    total_wells_with_controls = total_wells + control_wells

    # Number of 384-well plates needed
    wells_per_plate = 384
    n_plates = math.ceil(total_wells_with_controls / wells_per_plate)

    # Scale hands-on time: base time per plate, with efficiency gains for batching
    base_hours = tmpl["hands_on_hours"]
    # First plate takes full time, each additional plate adds ~60% of base
    hands_on_hours = base_hours + max(0, n_plates - 1) * base_hours * 0.6
    hands_on_days = round(hands_on_hours / 8.0, 1)

    # Calendar days: base + extra days for additional plates (batching helps)
    base_cal_days = tmpl["calendar_days"]
    extra_plate_days = max(0, math.ceil((n_plates - 1) / 4))  # ~4 plates per batch
    calendar_days = base_cal_days + extra_plate_days

    # Cost
    total_cost = n_plates * tmpl["cost_per_plate"]

    return {
        "summary": (
            f"{tmpl['name']}: {n_compounds} compounds x {n_doses} doses x {n_replicates} replicates = "
            f"{total_wells_with_controls} wells ({n_plates} plates). "
            f"Estimated {hands_on_hours:.1f}h hands-on ({hands_on_days} days), "
            f"{calendar_days} calendar days, ~${total_cost:,}"
        ),
        "assay_type": assay_type,
        "assay_name": tmpl["name"],
        "n_compounds": n_compounds,
        "n_doses": n_doses,
        "n_replicates": n_replicates,
        "total_wells": total_wells_with_controls,
        "n_plates": n_plates,
        "hands_on_hours": round(hands_on_hours, 1),
        "hands_on_days": hands_on_days,
        "calendar_days": calendar_days,
        "estimated_cost": total_cost,
        "cost_per_plate": tmpl["cost_per_plate"],
    }
