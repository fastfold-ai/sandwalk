"""omics.cellxgene_fetch: download an h5ad from CELLxGENE. Split from tools/omics.py."""
from tools import registry
from tools.omics_cellxgene_search import _CELLXGENE_API

from tools import omics as _omics


@registry.register(
    name="omics.cellxgene_fetch",
    description="Download an h5ad dataset from CELLxGENE Discover",
    category="omics",
    parameters={
        "dataset_id": "CELLxGENE dataset ID (from omics.cellxgene_search results)",
    },
    usage_guide=(
        "Download a single-cell dataset from CELLxGENE. Requires a dataset_id "
        "from omics.cellxgene_search results. Downloads as h5ad format."
    ),
)
def cellxgene_fetch(dataset_id: str, **kwargs) -> dict:
    """Download an h5ad dataset from CELLxGENE."""
    if not dataset_id or not dataset_id.strip():
        return {"error": "dataset_id is required", "summary": "No dataset_id provided"}

    dataset_id = dataset_id.strip()

    # Get asset list
    assets_url = f"{_CELLXGENE_API}/datasets/{dataset_id}/assets"
    assets, error = _omics.request_json("GET", assets_url, timeout=15)
    if error:
        return {"error": f"Failed to get assets: {error}", "summary": f"CELLxGENE asset lookup failed: {error}"}

    if not isinstance(assets, list) or not assets:
        return {
            "error": f"No downloadable assets found for dataset {dataset_id}",
            "summary": f"No assets for dataset {dataset_id}",
        }

    # Find h5ad asset
    h5ad_asset = None
    for asset in assets:
        filetype = (asset.get("filetype") or asset.get("file_type") or "").lower()
        filename = (asset.get("filename") or "").lower()
        if "h5ad" in filetype or filename.endswith(".h5ad"):
            h5ad_asset = asset
            break

    if not h5ad_asset:
        # Fall back to first asset
        h5ad_asset = assets[0]

    download_url = h5ad_asset.get("presigned_url") or h5ad_asset.get("url", "")
    if not download_url:
        return {
            "error": "No download URL in asset metadata",
            "summary": "CELLxGENE asset has no download URL",
        }

    filename = h5ad_asset.get("filename", f"{dataset_id}.h5ad")
    dest_dir = _omics._downloads_dir() / "cellxgene" / dataset_id
    dest = dest_dir / filename

    if dest.exists():
        size_mb = round(dest.stat().st_size / (1024 * 1024), 2)
        return {
            "path": str(dest),
            "dataset_id": dataset_id,
            "size_mb": size_mb,
            "summary": f"Already downloaded: {filename} ({size_mb} MB)",
        }

    path, error = _omics._stream_download(download_url, dest)
    if error:
        return {"error": error, "dataset_id": dataset_id, "summary": f"Download failed: {error}"}

    size_mb = round(path.stat().st_size / (1024 * 1024), 2)
    return {
        "path": str(path),
        "dataset_id": dataset_id,
        "filename": filename,
        "size_mb": size_mb,
        "summary": f"Downloaded CELLxGENE dataset {dataset_id} ({size_mb} MB) to {path}",
    }
