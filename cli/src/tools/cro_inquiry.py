"""CRO tools: draft and (dry-run) send inquiry emails to a CRO."""

from tools import registry


@registry.register(
    name="cro.draft_inquiry",
    description="Draft a professional inquiry email to a CRO (from built-in directory) for a specific experiment",
    category="cro",
    parameters={
        "cro_id": "CRO identifier (e.g. 'reaction-biology')",
        "experiment_description": "Description of the experiment / assay needed",
        "compound": "Compound name or identifier (optional)",
        "target": "Target protein or gene (optional)",
        "timeline": "Desired timeline (optional, e.g. '3 months')",
    },
    usage_guide="You've selected a CRO and need to draft a professional inquiry email. Run after cro.match_experiment to contact the top-ranked CRO.",
)
def draft_inquiry(cro_id: str, experiment_description: str,
                  compound: str = None, target: str = None,
                  timeline: str = None, **kwargs) -> dict:
    """Generate a professional inquiry email to a CRO."""
    from tools.cro import _load_cro_db  # indirect import so tests can patch tools.cro._load_cro_db

    db = _load_cro_db()
    id_to_cro = {cro["id"]: cro for cro in db}

    cro = id_to_cro.get(cro_id)
    if not cro:
        return {"error": f"CRO '{cro_id}' not found in database", "summary": f"CRO '{cro_id}' not found in database"}
    subject = f"Inquiry: {experiment_description[:60]}"
    if compound:
        subject = f"Inquiry: {experiment_description[:40]} — {compound}"

    body_parts = [
        f"Dear {cro['name']} Team,",
        "",
        "I am writing to inquire about your services for the following study:",
        "",
        f"**Experiment:** {experiment_description}",
    ]
    if target:
        body_parts.append(f"**Target:** {target}")
    if compound:
        body_parts.append(f"**Compound:** {compound}")
    if timeline:
        body_parts.append(f"**Desired Timeline:** {timeline}")

    body_parts.extend([
        "",
        "We are interested in understanding:",
        "1. Your capacity and availability for this type of study",
        "2. Estimated timeline and pricing",
        "3. Any relevant experience with similar projects (particularly in targeted protein degradation)",
        "4. Required compound quantity and format",
        "",
        "Could you please provide a preliminary quote and study outline? We would also welcome a call to discuss the details.",
        "",
        "Thank you for your time.",
        "",
        "Best regards",
    ])

    body = "\n".join(body_parts)

    return {
        "summary": f"[PLACEHOLDER] Drafted inquiry to {cro['name']} ({cro['contact_email']}) re: {experiment_description[:50]} — verify CRO contact details before sending",
        "placeholder": True,
        "cro_id": cro_id,
        "cro_name": cro["name"],
        "to_email": cro["contact_email"],
        "subject": subject,
        "body": body,
    }


@registry.register(
    name="cro.send_inquiry",
    description="Send a drafted inquiry email to a CRO (dry_run by default)",
    category="cro",
    parameters={
        "cro_id": "CRO identifier",
        "subject": "Email subject line",
        "body": "Email body text",
        "dry_run": "If True (default), simulate sending without actually delivering",
    },
    usage_guide="You have a finalized inquiry email and want to send it to the CRO. Always runs in dry_run mode unless explicitly overridden.",
)
def send_inquiry(cro_id: str, subject: str, body: str,
                 dry_run: bool = True, **kwargs) -> dict:
    """Send an inquiry email to a CRO."""
    from tools.cro import _load_cro_db  # indirect import so tests can patch tools.cro._load_cro_db

    db = _load_cro_db()
    id_to_cro = {cro["id"]: cro for cro in db}

    cro = id_to_cro.get(cro_id)
    if not cro:
        return {"error": f"CRO '{cro_id}' not found in database", "summary": f"CRO '{cro_id}' not found in database"}
    to_email = cro["contact_email"]

    if dry_run:
        return {
            "summary": f"[DRY RUN] Would send email to {cro['name']} ({to_email}): {subject}",
            "dry_run": True,
            "to_email": to_email,
            "cro_name": cro["name"],
            "subject": subject,
            "body": body,
        }

    # Attempt to send via notification module
    try:
        from tools.notification import send_email
        result = send_email(to=to_email, subject=subject, body=body)
        return {
            "summary": f"Sent inquiry to {cro['name']} ({to_email}): {subject}",
            "dry_run": False,
            "to_email": to_email,
            "cro_name": cro["name"],
            "subject": subject,
            "send_result": result,
        }
    except ImportError:
        return {
            "summary": f"[FAILED] notification module not available — email not sent to {to_email}",
            "dry_run": False,
            "error": "notification.send_email not available. Install notification module or use dry_run=True.",
            "to_email": to_email,
            "subject": subject,
            "body": body,
        }
