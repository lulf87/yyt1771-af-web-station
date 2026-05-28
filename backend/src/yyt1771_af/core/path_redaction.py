from __future__ import annotations

import re
from pathlib import PurePosixPath, PureWindowsPath
from typing import Any

WINDOWS_ABSOLUTE_PATH = re.compile(r"^[A-Za-z]:[\\/].+")
WINDOWS_UNC_PATH = re.compile(r"^\\\\[^\\]+\\[^\\]+\\?.*")
POSIX_ABSOLUTE_PATH = re.compile(r"^/.+")
PATH_KEY_PATTERN = re.compile(r"(^path$|_path$|path_|_dir$|dir$|_file$|file_path$|frames_dir$)")


def safe_path_label(value: str) -> str:
    if "\\" in value or WINDOWS_ABSOLUTE_PATH.match(value) or WINDOWS_UNC_PATH.match(value):
        name = PureWindowsPath(value).name
    else:
        name = PurePosixPath(value).name
    return name or "redacted_path"


def sanitize_path_metadata(value: Any, *, key: str | None = None) -> Any:
    if isinstance(value, dict):
        return {
            str(child_key): sanitize_path_metadata(child_value, key=str(child_key))
            for child_key, child_value in value.items()
        }
    if isinstance(value, list):
        return [sanitize_path_metadata(item, key=key) for item in value]
    if isinstance(value, tuple):
        return [sanitize_path_metadata(item, key=key) for item in value]
    if isinstance(value, str) and should_redact_path(value, key):
        return safe_path_label(value)
    return value


def should_redact_path(value: str, key: str | None) -> bool:
    normalized_key = (key or "").lower()
    return (
        _path_key(normalized_key)
        or bool(WINDOWS_ABSOLUTE_PATH.match(value))
        or bool(WINDOWS_UNC_PATH.match(value))
        or bool(POSIX_ABSOLUTE_PATH.match(value))
    ) and safe_path_label(value) != value


def _path_key(key: str) -> bool:
    return bool(PATH_KEY_PATTERN.search(key))
