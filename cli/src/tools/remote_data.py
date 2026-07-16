"""remote_data: split into tools/remote_data_base.py + tools/remote_data_part*.py."""
from tools.remote_data_part1 import (
    _get_endpoint,
    _no_endpoint_error,
    query,
)
from tools.remote_data_part2 import (
    list_datasets,
)
