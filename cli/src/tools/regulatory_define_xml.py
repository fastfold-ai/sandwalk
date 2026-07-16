"""regulatory.define_xml_lint: Define-XML structural/referential linting.

Split from tools/regulatory.py.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from tools import registry
from tools.regulatory_common import (
    _attr_by_local_name,
    _duplicate_oids,
    _issue,
    _local_name,
    _score_quality,
)


@registry.register(
    name="regulatory.define_xml_lint",
    description="Lint a Define-XML file for structural integrity and common referential issues",
    category="regulatory",
    parameters={
        "define_xml_path": "Path to define.xml file",
        "strict": "If true, missing optional metadata is elevated to warning/error",
        "max_issues": "Maximum issues returned (default 100)",
    },
    usage_guide=(
        "Use to preflight Define-XML before package delivery. Checks parseability, "
        "core structure, and reference integrity (ItemRef/CodeListRef/ValueListRef)."
    ),
)
def define_xml_lint(
    define_xml_path: str,
    strict: bool = False,
    max_issues: int = 100,
    **kwargs,
) -> dict:
    """Run structural and referential lint checks for Define-XML."""
    del kwargs

    if not define_xml_path:
        return {"summary": "define_xml_path is required.", "error": "missing_define_xml_path"}

    path = Path(define_xml_path).expanduser()
    if not path.exists():
        return {"summary": f"Define-XML file not found: {path}", "error": "file_not_found"}
    if path.is_dir():
        return {"summary": f"define_xml_path must be a file: {path}", "error": "path_is_directory"}

    try:
        tree = ET.parse(path)
    except ET.ParseError as exc:
        return {"summary": f"Invalid XML: {exc}", "error": "xml_parse_error"}
    except Exception as exc:
        return {"summary": f"Failed to read Define-XML: {exc}", "error": "read_failed"}

    root = tree.getroot()
    issues: list[dict] = []

    if _local_name(root.tag) != "ODM":
        _issue(issues, "error", "root_not_odm", "Root element is not ODM.")

    studies = [x for x in root.iter() if _local_name(x.tag) == "Study"]
    mdvs = [x for x in root.iter() if _local_name(x.tag) == "MetaDataVersion"]
    item_defs = [x for x in root.iter() if _local_name(x.tag) == "ItemDef"]
    item_groups = [x for x in root.iter() if _local_name(x.tag) == "ItemGroupDef"]
    code_lists = [x for x in root.iter() if _local_name(x.tag) == "CodeList"]
    value_lists = [x for x in root.iter() if _local_name(x.tag) == "ValueListDef"]
    where_defs = [x for x in root.iter() if _local_name(x.tag) == "WhereClauseDef"]
    leaf_nodes = [x for x in root.iter() if _local_name(x.tag).lower() == "leaf"]

    if not studies:
        _issue(issues, "error", "missing_study", "No Study element found.")
    if not mdvs:
        _issue(issues, "error", "missing_metadataversion", "No MetaDataVersion element found.")
    if not item_defs:
        _issue(issues, "error", "missing_itemdefs", "No ItemDef elements found.")
    if not item_groups:
        _issue(issues, "error", "missing_itemgroups", "No ItemGroupDef elements found.")

    for oid in sorted(_duplicate_oids(item_defs)):
        _issue(issues, "error", "duplicate_itemdef_oid", f"Duplicate ItemDef OID: {oid}")
    for oid in sorted(_duplicate_oids(item_groups)):
        _issue(issues, "error", "duplicate_itemgroup_oid", f"Duplicate ItemGroupDef OID: {oid}")
    for oid in sorted(_duplicate_oids(code_lists)):
        _issue(issues, "error", "duplicate_codelist_oid", f"Duplicate CodeList OID: {oid}")

    item_oids = {str(x.attrib.get("OID", "")).strip() for x in item_defs if x.attrib.get("OID")}
    codelist_oids = {
        str(x.attrib.get("OID", "")).strip()
        for x in code_lists
        if x.attrib.get("OID")
    }
    valuelist_oids = {
        str(x.attrib.get("OID", "")).strip()
        for x in value_lists
        if x.attrib.get("OID")
    }
    where_oids = {
        str(x.attrib.get("OID", "")).strip()
        for x in where_defs
        if x.attrib.get("OID")
    }

    for item in item_defs:
        oid = str(item.attrib.get("OID", "")).strip() or "<missing>"
        if not str(item.attrib.get("Name", "")).strip():
            _issue(issues, "error", "itemdef_missing_name", "ItemDef missing Name.", field=oid)
        if not str(item.attrib.get("DataType", "")).strip():
            _issue(issues, "error", "itemdef_missing_datatype", "ItemDef missing DataType.", field=oid)

    for ref in [x for x in root.iter() if _local_name(x.tag) == "ItemRef"]:
        item_oid = str(ref.attrib.get("ItemOID", "")).strip()
        if not item_oid:
            _issue(issues, "error", "itemref_missing_itemoid", "ItemRef missing ItemOID.")
            continue
        if item_oid not in item_oids:
            _issue(
                issues,
                "error",
                "itemref_unknown_itemoid",
                f"ItemRef points to unknown ItemDef OID: {item_oid}",
            )

    for ref in [x for x in root.iter() if _local_name(x.tag) == "CodeListRef"]:
        code_oid = str(ref.attrib.get("CodeListOID", "")).strip()
        if not code_oid:
            _issue(issues, "error", "codelistref_missing_oid", "CodeListRef missing CodeListOID.")
            continue
        if code_oid not in codelist_oids:
            _issue(
                issues,
                "error",
                "codelistref_unknown_oid",
                f"CodeListRef points to unknown CodeList OID: {code_oid}",
            )

    for ref in [x for x in root.iter() if _local_name(x.tag) == "ValueListRef"]:
        value_oid = str(ref.attrib.get("ValueListOID", "")).strip()
        if not value_oid:
            _issue(issues, "error", "valuelistref_missing_oid", "ValueListRef missing ValueListOID.")
            continue
        if value_oid not in valuelist_oids:
            _issue(
                issues,
                "error",
                "valuelistref_unknown_oid",
                f"ValueListRef points to unknown ValueListDef OID: {value_oid}",
            )

    for ref in [x for x in root.iter() if _local_name(x.tag) == "WhereClauseRef"]:
        where_oid = str(ref.attrib.get("WhereClauseOID", "")).strip()
        if not where_oid:
            _issue(issues, "warning", "whereclauseref_missing_oid", "WhereClauseRef missing OID.")
            continue
        if where_oids and where_oid not in where_oids:
            _issue(
                issues,
                "error",
                "whereclauseref_unknown_oid",
                f"WhereClauseRef points to unknown WhereClauseDef OID: {where_oid}",
            )

    if not leaf_nodes and strict:
        _issue(issues, "warning", "missing_leaf", "No def:leaf nodes found for data/metadata files.")

    for leaf in leaf_nodes:
        href = _attr_by_local_name(leaf, "href")
        if not href:
            _issue(issues, "error", "leaf_missing_href", "def:leaf is missing xlink:href.")

    n_errors = sum(1 for x in issues if x["severity"] == "error")
    n_warnings = sum(1 for x in issues if x["severity"] == "warning")
    score = _score_quality(n_errors, n_warnings)
    max_issues = max(1, int(max_issues or 100))

    summary = (
        f"Define-XML lint for {path.name}: {n_errors} error(s), {n_warnings} warning(s), "
        f"quality score {score}/100."
    )

    return {
        "summary": summary,
        "define_xml_path": str(path),
        "error_count": n_errors,
        "warning_count": n_warnings,
        "quality_score": score,
        "counts": {
            "study": len(studies),
            "metadataversion": len(mdvs),
            "itemdef": len(item_defs),
            "itemgroupdef": len(item_groups),
            "codelist": len(code_lists),
            "valuelistdef": len(value_lists),
            "leaf": len(leaf_nodes),
        },
        "issues": issues[:max_issues],
    }
