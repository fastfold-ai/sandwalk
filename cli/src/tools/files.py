"""
File I/O tools for ct.

Read files, write reports/CSV, edit/create/delete files, and search file contents.
Restricted to safe directories (~/.sandwalk/, config-specified paths, and CWD).

Split across tools/files_paths.py (path-safety helpers), tools/files_rw.py
(read_file/edit_file/create_file/delete_file), tools/files_ops.py
(move_file/copy_file/create_directory/extract_archive), tools/files_search.py
(list_directory/search_files/search_content), and tools/files_reports.py
(write_report/write_csv/list_outputs); re-exported here for backward
compatibility. This module is the canonical patch target for tests
(e.g. ``patch("tools.files.Path.cwd")``); since ``Path`` is the same class
object everywhere, patching it via ``tools.files.Path`` affects every
submodule regardless of which one performs the call.
"""

from pathlib import Path

from agent.config import CONFIG_DIR, LEGACY_CONFIG_DIRS
from tools.files_ops import copy_file, create_directory, extract_archive, move_file
from tools.files_paths import (
    _PROTECTED_PATTERNS,
    _allowed_paths,
    _is_allowed,
    _is_protected,
    _is_within_cwd,
    _output_dir,
    _resolve_cwd_path,
    _resolve_output_path,
)
from tools.files_reports import list_outputs, write_csv, write_report
from tools.files_rw import create_file, delete_file, edit_file, read_file
from tools.files_search import list_directory, search_content, search_files

__all__ = [
    "Path",
    "CONFIG_DIR",
    "LEGACY_CONFIG_DIRS",
    "_allowed_paths",
    "_is_allowed",
    "_is_within_cwd",
    "_PROTECTED_PATTERNS",
    "_is_protected",
    "_output_dir",
    "_resolve_output_path",
    "_resolve_cwd_path",
    "read_file",
    "edit_file",
    "create_file",
    "delete_file",
    "move_file",
    "copy_file",
    "create_directory",
    "extract_archive",
    "list_directory",
    "search_files",
    "search_content",
    "write_report",
    "write_csv",
    "list_outputs",
]
