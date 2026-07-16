"""
Dataset downloader for ct.

Manages downloading and caching of common drug discovery datasets.
Supports automatic downloads for open-access datasets and guided
instructions for datasets requiring portal authentication.
"""

from agent.config import Config
from data.downloader.catalog import console, DATASETS, DOWNLOAD_TIMEOUT
from data.downloader.fetch import _download_file
from data.downloader.ops import download_all, download_dataset
from data.downloader.prism_builder import _download_prism, _PRISM_FILES
from data.downloader.removal import remove_dataset
from data.downloader.reporting import dataset_catalog, dataset_status, list_dataset_records
from data.downloader.util import _dataset_disk_size, _format_size

__all__ = [
    "Config",
    "console",
    "DATASETS",
    "DOWNLOAD_TIMEOUT",
    "download_dataset",
    "download_all",
    "dataset_catalog",
    "dataset_status",
    "list_dataset_records",
    "remove_dataset",
    "_download_file",
    "_download_prism",
    "_PRISM_FILES",
    "_format_size",
    "_dataset_disk_size",
]
