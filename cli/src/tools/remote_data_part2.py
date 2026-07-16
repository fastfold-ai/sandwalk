"""remote_data — part 2 of split module. See tools/remote_data.py."""
from tools.remote_data_base import httpx, registry
from tools.remote_data_part1 import _get_endpoint, _no_endpoint_error

@registry.register(
    name="remote_data.list_datasets",
    description="List datasets available on the hosted fastfold Data API",
    category="remote_data",
    parameters={},
    usage_guide=(
        "You want to see what datasets are available on the configured data API. "
        "Run this first to discover available data before querying."
    ),
)
def list_datasets(**kwargs) -> dict:
    """List datasets available on the Data API."""
    endpoint = _get_endpoint()
    if not endpoint:
        return _no_endpoint_error()

    try:
        resp = httpx.get(f"{endpoint}/datasets", timeout=10)

        if resp.status_code != 200:
            return {
                "error": f"Data API error: HTTP {resp.status_code}",
                "summary": f"Failed to list datasets: HTTP {resp.status_code}",
            }

        datasets = resp.json()
        if not datasets:
            return {
                "summary": "No datasets available on the Data API.",
                "datasets": [],
            }

        names = [d["name"] for d in datasets]
        summary = f"Data API has {len(datasets)} datasets: {', '.join(names)}"

        return {
            "summary": summary,
            "datasets": datasets,
        }

    except httpx.ConnectError:
        return {
            "error": f"Cannot connect to Data API at {endpoint}",
            "summary": f"Data API unreachable at {endpoint}. Check the server is running.",
        }
    except httpx.HTTPError as e:
        return {
            "error": f"Data API request failed: {e}",
            "summary": f"Failed to list datasets: {e}",
        }
