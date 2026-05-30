from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel

from yyt1771_af.core.config import CONFIGS_DIR, load_config_file, resolve_configured_path
from yyt1771_af.core.path_redaction import safe_path_label

DEFAULT_DATASET_ID = "default"
DATASETS_FILE_ENV = "YYT1771_AF_OFFLINE_DATASETS_FILE"
OFFLINE_DIR_ENV = "YYT1771_AF_OFFLINE_DIR"
LOCAL_DATASETS_FILENAMES = (
    "offline_datasets.local.json",
    "offline_datasets.local.yaml",
    "offline_datasets.local.yml",
)


@dataclass(frozen=True, slots=True)
class OfflineDataset:
    dataset_id: str
    label: str
    frames_dir: Path


class OfflineDatasetInfo(BaseModel):
    """Public dataset description that never exposes an absolute path."""

    dataset_id: str
    label: str
    available: bool


def list_offline_datasets() -> list[OfflineDataset]:
    """Return the configured simulation material datasets.

    Datasets come from a local (git-ignored) config file. When no config file is
    present, fall back to the single dataset referenced by ``YYT1771_AF_OFFLINE_DIR``
    so existing single-folder setups keep working.
    """

    datasets = _load_configured_datasets()
    if datasets:
        return datasets
    return _env_fallback_datasets()


def list_offline_dataset_infos() -> list[OfflineDatasetInfo]:
    return [
        OfflineDatasetInfo(
            dataset_id=dataset.dataset_id,
            label=dataset.label,
            available=dataset.frames_dir.exists() and dataset.frames_dir.is_dir(),
        )
        for dataset in list_offline_datasets()
    ]


def resolve_offline_dataset_dir(dataset_id: str) -> Path:
    for dataset in list_offline_datasets():
        if dataset.dataset_id == dataset_id:
            if not dataset.frames_dir.exists() or not dataset.frames_dir.is_dir():
                raise FileNotFoundError("selected simulation dataset folder is not available")
            return dataset.frames_dir
    raise FileNotFoundError("selected simulation dataset is not configured")


def _load_configured_datasets() -> list[OfflineDataset]:
    config_path = _datasets_config_path()
    if config_path is None:
        return []
    payload = load_config_file(config_path)
    raw_entries = payload.get("datasets")
    if not isinstance(raw_entries, list):
        return []

    datasets: list[OfflineDataset] = []
    seen_ids: set[str] = set()
    for raw_entry in raw_entries:
        if not isinstance(raw_entry, dict):
            continue
        frames_dir_value = raw_entry.get("frames_dir")
        if not isinstance(frames_dir_value, str) or frames_dir_value.strip() == "":
            continue
        frames_dir = resolve_configured_path(Path(frames_dir_value))
        dataset_id = str(raw_entry.get("id") or frames_dir.name or DEFAULT_DATASET_ID)
        if dataset_id in seen_ids:
            continue
        seen_ids.add(dataset_id)
        label = str(raw_entry.get("label") or dataset_id)
        datasets.append(
            OfflineDataset(dataset_id=dataset_id, label=label, frames_dir=frames_dir)
        )
    return datasets


def _env_fallback_datasets() -> list[OfflineDataset]:
    value = os.environ.get(OFFLINE_DIR_ENV)
    if value is None or value.strip() == "":
        return []
    frames_dir = resolve_configured_path(Path(value))
    return [
        OfflineDataset(
            dataset_id=DEFAULT_DATASET_ID,
            label=safe_path_label(str(frames_dir)),
            frames_dir=frames_dir,
        )
    ]


def _datasets_config_path() -> Path | None:
    override = os.environ.get(DATASETS_FILE_ENV)
    if override is not None and override.strip() != "":
        candidate = resolve_configured_path(Path(override))
        return candidate if candidate.is_file() else None

    for filename in LOCAL_DATASETS_FILENAMES:
        candidate = CONFIGS_DIR / "local" / filename
        if candidate.is_file():
            return candidate
    return None
