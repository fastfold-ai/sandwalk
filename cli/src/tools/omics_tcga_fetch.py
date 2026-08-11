"""omics.tcga_fetch: download a TCGA/GDC file. Split from tools/omics.py."""
from tools import registry

from tools import omics as _omics
from tools.omics_tcga_search import _GDC_API


@registry.register(
    name="omics.tcga_fetch",
    description="Download a data file from TCGA/GDC",
    category="omics",
    parameters={
        "file_id": "GDC file UUID to download",
        "project_id": "GDC project ID (optional, used to search for files if file_id not provided)",
    },
    usage_guide=(
        "Download a specific file from GDC by UUID. If only project_id is given, "
        "searches for the most relevant gene expression file and downloads it."
    ),
)
def tcga_fetch(file_id: str = "", project_id: str = "", **kwargs) -> dict:
    """Download a data file from TCGA/GDC."""
    import json

    if not file_id and not project_id:
        return {
            "error": "Either file_id or project_id is required",
            "summary": "No file_id or project_id provided",
        }

    # If no file_id, search for one from the project
    if not file_id:
        files_url = f"{_GDC_API}/files"
        filters = {
            "op": "and",
            "content": [
                {"op": "=", "content": {"field": "cases.project.project_id", "value": project_id}},
                {"op": "=", "content": {"field": "data_type", "value": "Gene Expression Quantification"}},
                {"op": "=", "content": {"field": "access", "value": "open"}},
            ],
        }
        params = {
            "filters": json.dumps(filters),
            "fields": "file_id,file_name,file_size,data_type",
            "size": "1",
            "format": "json",
        }
        data, error = _omics.request_json("GET", files_url, params=params, timeout=15)
        if error:
            return {"error": f"File search failed: {error}", "summary": f"GDC file search error: {error}"}

        hits = data.get("data", {}).get("hits", [])
        if not hits:
            return {
                "error": f"No open-access files found for project {project_id}",
                "summary": f"No downloadable files for {project_id}",
            }
        file_id = hits[0].get("file_id", "")
        file_name = hits[0].get("file_name", f"{file_id}.gz")
    else:
        file_name = f"{file_id}.gz"

    # Download the file
    download_url = f"{_GDC_API}/data/{file_id}"
    label = project_id or file_id[:12]
    dest_dir = _omics._downloads_dir() / "tcga" / label
    dest = dest_dir / file_name

    if dest.exists():
        size_mb = round(dest.stat().st_size / (1024 * 1024), 2)
        return {
            "path": str(dest),
            "file_id": file_id,
            "project_id": project_id,
            "size_mb": size_mb,
            "summary": f"Already downloaded: {file_name} ({size_mb} MB)",
        }

    path, error = _omics._stream_download(download_url, dest)
    if error:
        return {"error": error, "file_id": file_id, "summary": f"Download failed: {error}"}

    size_mb = round(path.stat().st_size / (1024 * 1024), 2)
    return {
        "path": str(path),
        "file_id": file_id,
        "project_id": project_id,
        "filename": file_name,
        "size_mb": size_mb,
        "summary": f"Downloaded GDC file {file_name} ({size_mb} MB) to {path}",
    }
