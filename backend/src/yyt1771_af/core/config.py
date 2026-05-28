from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from yyt1771_af.core.models import (
    BalloonEnvelopeDetectorParams,
    RotatedRoi,
    SegmentationParams,
    WireStripDetectorParams,
)
from yyt1771_af.core.statuses import TargetFamily

PROJECT_ROOT = Path(__file__).resolve().parents[4]
CONFIGS_DIR = PROJECT_ROOT / "configs"


class CameraProfileConfig(BaseModel):
    profile_name: str
    mode: str | None = None
    camera: dict[str, Any] = Field(default_factory=dict)
    runtime: dict[str, Any] = Field(default_factory=dict)
    frontend: dict[str, Any] = Field(default_factory=dict)
    temperature_controller: dict[str, Any] = Field(default_factory=dict)


class OfflineValidationConfig(BaseModel):
    target_family: TargetFamily | None = None
    roi: RotatedRoi
    recipe: dict[str, Any] = Field(default_factory=dict)
    frames_dir: Path | None = None
    fps: float | None = Field(default=None, gt=0.0)
    output_dir: Path | None = None
    dataset_label: str | None = None

    @property
    def recipe_name(self) -> str | None:
        name = self.recipe.get("name")
        return str(name) if name is not None else None


@dataclass(frozen=True, slots=True)
class DetectorRecipeConfig:
    name: str
    target_family: TargetFamily
    segmentation: SegmentationParams
    detector: BalloonEnvelopeDetectorParams | WireStripDetectorParams


def load_config_file(path: Path) -> dict[str, Any]:
    config_path = Path(path)
    suffix = config_path.suffix.lower()
    text = config_path.read_text(encoding="utf-8")
    if suffix == ".json":
        payload = json.loads(text)
    elif suffix in {".yaml", ".yml"}:
        payload = yaml.safe_load(text)
    else:
        raise ValueError(f"unsupported config file extension: {config_path.suffix}")

    if payload is None:
        return {}
    if not isinstance(payload, Mapping):
        raise ValueError("config root must be a mapping")
    return dict(payload)


def load_camera_profile_config(profile: str | Path) -> CameraProfileConfig:
    path = _resolve_config_reference(profile, CONFIGS_DIR / "profiles")
    return CameraProfileConfig.model_validate(load_config_file(path))


def load_offline_validation_config(path: Path) -> OfflineValidationConfig:
    return OfflineValidationConfig.model_validate(load_config_file(path))


def load_detector_recipe_config(
    target_family: TargetFamily,
    recipe_name: str | None = None,
) -> DetectorRecipeConfig:
    selected_name = recipe_name or _default_recipe_name(target_family)
    path = _find_config_reference(selected_name, CONFIGS_DIR / "recipes")
    if path is None and recipe_name is not None:
        path = _find_config_reference(_default_recipe_name(target_family), CONFIGS_DIR / "recipes")

    payload = load_config_file(path) if path is not None else {}
    configured_target = TargetFamily(payload.get("target_family", target_family.value))
    if configured_target is not target_family:
        raise ValueError(
            f"recipe {selected_name!r} target_family {configured_target.value!r} "
            f"does not match requested {target_family.value!r}"
        )

    segmentation = SegmentationParams.model_validate(payload.get("segmentation") or {})
    detector_payload = payload.get("detector") or {}
    if target_family is TargetFamily.BALLOON_ENVELOPE:
        detector = BalloonEnvelopeDetectorParams.model_validate(detector_payload)
    else:
        detector = WireStripDetectorParams.model_validate(detector_payload)

    return DetectorRecipeConfig(
        name=str(recipe_name or payload.get("name") or selected_name),
        target_family=target_family,
        segmentation=segmentation,
        detector=detector,
    )


def resolve_configured_path(value: str | Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return (PROJECT_ROOT / path).resolve()


def _default_recipe_name(target_family: TargetFamily) -> str:
    if target_family is TargetFamily.BALLOON_ENVELOPE:
        return "balloon_envelope_default"
    return "wire_strip_default"


def _resolve_config_reference(reference: str | Path, folder: Path) -> Path:
    path = _find_config_reference(reference, folder)
    if path is None:
        raise FileNotFoundError(f"config not found: {reference}")
    return path


def _find_config_reference(reference: str | Path, folder: Path) -> Path | None:
    raw_path = Path(reference)
    candidates: list[Path]
    if raw_path.suffix.lower() in {".json", ".yaml", ".yml"}:
        candidates = [raw_path]
        if not raw_path.is_absolute():
            candidates.append(folder / raw_path.name)
    else:
        candidates = [
            raw_path,
            folder / f"{raw_path.name}.yaml",
            folder / f"{raw_path.name}.yml",
            folder / f"{raw_path.name}.json",
        ]

    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate
    return None
