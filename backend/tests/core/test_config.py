from __future__ import annotations

import json
from pathlib import Path

from yyt1771_af.core.config import (
    load_camera_profile_config,
    load_config_file,
    load_detector_recipe_config,
    load_offline_validation_config,
)
from yyt1771_af.core.statuses import TargetFamily


def test_load_config_file_supports_json_and_yaml(tmp_path: Path) -> None:
    json_path = tmp_path / "config.json"
    yaml_path = tmp_path / "config.yaml"
    json_path.write_text(json.dumps({"name": "json_config"}), encoding="utf-8")
    yaml_path.write_text("name: yaml_config\n", encoding="utf-8")

    assert load_config_file(json_path) == {"name": "json_config"}
    assert load_config_file(yaml_path) == {"name": "yaml_config"}


def test_committed_offline_validation_examples_are_readable() -> None:
    json_config = load_offline_validation_config(
        Path("configs/validation/offline_real_capture.example.json")
    )
    yaml_config = load_offline_validation_config(
        Path("configs/validation/offline_real_capture.example.yaml")
    )
    balloon_roi = load_offline_validation_config(
        Path("configs/validation/roi_balloon.example.json")
    )
    wire_roi = load_offline_validation_config(Path("configs/validation/roi_wire.example.json"))

    assert json_config.target_family is TargetFamily.BALLOON_ENVELOPE
    assert yaml_config.target_family is TargetFamily.BALLOON_ENVELOPE
    assert balloon_roi.target_family is TargetFamily.BALLOON_ENVELOPE
    assert wire_roi.target_family is TargetFamily.WIRE_STRIP
    assert json_config.roi.coordinate_space.value == "acquisition"
    assert yaml_config.recipe_name == "offline_real_capture_baseline"


def test_camera_profile_and_detector_recipe_configs_are_readable() -> None:
    profile = load_camera_profile_config("dev_offline")
    balloon_recipe = load_detector_recipe_config(
        TargetFamily.BALLOON_ENVELOPE,
        "balloon_envelope_default",
    )
    wire_recipe = load_detector_recipe_config(TargetFamily.WIRE_STRIP, "wire_strip_default")

    assert profile.camera["type"] == "offline_folder"
    assert balloon_recipe.segmentation.close_kernel == 11
    assert balloon_recipe.detector.detector_kind.value == "balloon_envelope_detector"
    assert wire_recipe.segmentation.threshold_mode == "fixed"
    assert wire_recipe.segmentation.polarity == "dark_on_light"
    assert wire_recipe.detector.measurement_mode == "wire_bundle_envelope"
    assert wire_recipe.detector.detector_kind.value == "wire_strip_detector"


def test_unknown_recipe_name_uses_target_defaults_with_requested_name() -> None:
    recipe = load_detector_recipe_config(TargetFamily.BALLOON_ENVELOPE, "local_roi_trial")

    assert recipe.name == "local_roi_trial"
    assert recipe.target_family is TargetFamily.BALLOON_ENVELOPE
    assert recipe.detector.detector_kind.value == "balloon_envelope_detector"
