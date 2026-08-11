"""Gene-set collection loaders (MSigDB)."""

from typing import Any


def load_msigdb(collection: str = "h") -> dict[str, Any]:
    """Load MSigDB gene sets."""
    import json

    from data.loaders import _find_file

    # Try both naming patterns: "h.all.v2024.1.Hs.json" and "c2.cp.kegg_legacy.v2024.1.Hs.json"
    for pattern in [f"{collection}.all.v2024.1.Hs.json", f"{collection}.v2024.1.Hs.json"]:
        path = _find_file(pattern, subdirs=["", "msigdb"])
        if path and path.exists():
            with open(path) as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
                return {"data": data}

    raise FileNotFoundError("MSigDB data not found. Run: sandwalk data pull msigdb")
