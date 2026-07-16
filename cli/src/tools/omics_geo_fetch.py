"""omics.geo_fetch: download a GEO dataset. Split from tools/omics.py."""
import re

from tools import registry

from tools import omics as _omics


@registry.register(
    name="omics.geo_fetch",
    description="Download a GEO dataset (expression matrix or supplementary files)",
    category="omics",
    parameters={
        "accession": "GEO accession (e.g., 'GSE12345')",
        "file_type": "Type to download: 'matrix', 'h5ad', 'supplementary' (default 'matrix')",
    },
    usage_guide=(
        "Download data from NCBI GEO after finding accessions with omics.geo_search. "
        "Use 'matrix' for series matrix files, 'supplementary' for raw/processed supplements."
    ),
)
def geo_fetch(accession: str, file_type: str = "matrix", **kwargs) -> dict:
    """Download a GEO dataset."""
    # Validate accession
    if not accession or not re.match(r"^GSE\d+$", accession.strip()):
        return {
            "error": f"Invalid GEO accession '{accession}'. Expected format: GSE12345",
            "summary": f"Invalid accession format: {accession}",
        }

    accession = accession.strip().upper()
    # GEO FTP path uses first 3+nnn digits: GSE12345 → GSE12nnn
    prefix = accession[:len(accession) - 3] + "nnn"

    dest_dir = _omics._downloads_dir() / "geo" / accession
    dest_dir.mkdir(parents=True, exist_ok=True)

    if file_type == "matrix":
        filename = f"{accession}_series_matrix.txt.gz"
        url = f"https://ftp.ncbi.nlm.nih.gov/geo/series/{prefix}/{accession}/matrix/{filename}"
        dest = dest_dir / filename

        if dest.exists():
            size_mb = round(dest.stat().st_size / (1024 * 1024), 2)
            return {
                "path": str(dest),
                "accession": accession,
                "file_type": file_type,
                "size_mb": size_mb,
                "summary": f"Already downloaded: {dest.name} ({size_mb} MB)",
            }

        path, error = _omics._stream_download(url, dest)
        if error:
            return {"error": error, "accession": accession, "summary": f"Download failed for {accession}: {error}"}

        size_mb = round(path.stat().st_size / (1024 * 1024), 2)
        return {
            "path": str(path),
            "accession": accession,
            "file_type": file_type,
            "size_mb": size_mb,
            "summary": f"Downloaded {accession} series matrix ({size_mb} MB) to {path}",
        }

    elif file_type in ("h5ad", "supplementary"):
        # List supplementary files page
        suppl_url = f"https://ftp.ncbi.nlm.nih.gov/geo/series/{prefix}/{accession}/suppl/"
        resp, error = _omics.request("GET", suppl_url, timeout=15, raise_for_status=False)
        if error:
            return {"error": f"Could not list supplementary files: {error}", "summary": f"Supplementary listing failed for {accession}"}

        # Parse HTML directory listing for file links
        text = resp.text if hasattr(resp, "text") else str(resp)
        links = re.findall(r'href="([^"]+)"', text)
        data_files = [l for l in links if not l.startswith("?") and not l.startswith("/") and l != "../"]

        if not data_files:
            return {
                "error": f"No supplementary files found for {accession}",
                "summary": f"No supplementary files available for {accession}",
            }

        # For h5ad, prefer .h5ad files; otherwise take first data file
        target = None
        if file_type == "h5ad":
            h5ad_files = [f for f in data_files if f.endswith(".h5ad") or f.endswith(".h5ad.gz")]
            if h5ad_files:
                target = h5ad_files[0]
            else:
                return {
                    "error": f"No h5ad files found in {accession} supplementary files",
                    "files_available": data_files[:10],
                    "summary": f"No h5ad files in {accession}. Available: {', '.join(data_files[:5])}",
                }
        else:
            target = data_files[0]

        file_url = f"{suppl_url}{target}"
        dest = dest_dir / target

        if dest.exists():
            size_mb = round(dest.stat().st_size / (1024 * 1024), 2)
            return {
                "path": str(dest),
                "accession": accession,
                "file_type": file_type,
                "filename": target,
                "size_mb": size_mb,
                "summary": f"Already downloaded: {target} ({size_mb} MB)",
            }

        path, error = _omics._stream_download(file_url, dest)
        if error:
            return {"error": error, "accession": accession, "summary": f"Download failed: {error}"}

        size_mb = round(path.stat().st_size / (1024 * 1024), 2)
        return {
            "path": str(path),
            "accession": accession,
            "file_type": file_type,
            "filename": target,
            "size_mb": size_mb,
            "summary": f"Downloaded {target} ({size_mb} MB) from {accession}",
        }

    else:
        return {
            "error": f"Invalid file_type '{file_type}'. Choose: matrix, h5ad, supplementary",
            "summary": f"Invalid file_type: {file_type}",
        }
