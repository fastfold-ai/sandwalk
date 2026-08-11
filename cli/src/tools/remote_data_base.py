"""
Remote data query tool — queries the hosted fastfold Data API.

Connects to a running fastfold Data API instance to query large datasets
(PerturbAtlas, ChEMBL, scPerturb, etc.) that are too large for local download.

Configure the endpoint with: sandwalk config set api.data_endpoint http://host:8000
Or set CT_DATA_ENDPOINT environment variable.
"""

import os

import httpx

from agent.config import Config
from tools import registry
