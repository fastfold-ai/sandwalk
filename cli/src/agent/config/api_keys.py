"""Merged API key registry used by ``config set``, ``keys_table``, and env sync."""

from .api_keys_extra import API_KEYS_EXTRA
from .api_keys_llm import API_KEYS_LLM

API_KEYS = {**API_KEYS_LLM, **API_KEYS_EXTRA}
