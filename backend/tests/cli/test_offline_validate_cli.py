from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from yyt1771_af.cli.offline_validate import main


def test_offline_validate_cli_uses_env_frames_dir_and_writes_summary(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    frames_dir = tmp_path / "frames"
    frames_dir.mkdir()
    y, x = np.indices((72, 96))
    image = np.full((72, 96), 230, dtype=np.uint8)
    image[((x - 40.0) / 18.0) ** 2 + ((y - 30.0) / 10.0) ** 2 <= 1.0] = 30
    for index in range(3):
        np.save(frames_dir / f"frame_{index + 1}.npy", image)

    roi_json = tmp_path / "roi.json"
    roi_json.write_text(
        json.dumps(
            {
                "target_family": "balloon_envelope",
                "roi": {
                    "center_x": 40.0,
                    "center_y": 30.0,
                    "width": 60.0,
                    "height": 36.0,
                    "angle_deg": 0.0,
                    "coordinate_space": "acquisition",
                },
                "recipe": {"name": "pytest"},
            }
        ),
        encoding="utf-8",
    )
    output_dir = tmp_path / "out"
    monkeypatch.setenv("YYT1771_AF_OFFLINE_DIR", str(frames_dir))

    exit_code = main(
        [
            "--target-family",
            "balloon_envelope",
            "--roi-json",
            str(roi_json),
            "--fps",
            "10",
            "--output-dir",
            str(output_dir),
            "--max-frames",
            "3",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "evaluation_summary.json" in captured.out
    assert (output_dir / "evaluation_summary.json").exists()


def test_offline_validate_cli_reads_yaml_config(
    tmp_path: Path,
    capsys,
) -> None:
    frames_dir = tmp_path / "frames"
    frames_dir.mkdir()
    image = np.full((48, 64), 230, dtype=np.uint8)
    image[18:30, 24:40] = 30
    np.save(frames_dir / "frame_1.npy", image)
    config_path = tmp_path / "offline.yaml"
    output_dir = tmp_path / "out"
    config_path.write_text(
        f"""
target_family: wire_strip
frames_dir: "{frames_dir}"
output_dir: "{output_dir}"
fps: 10.0
roi:
  center_x: 32.0
  center_y: 24.0
  width: 30.0
  height: 24.0
  angle_deg: 0.0
  coordinate_space: acquisition
recipe:
  name: yaml_cli_trial
""",
        encoding="utf-8",
    )

    exit_code = main(["--config", str(config_path), "--max-frames", "1"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "evaluation_summary.json" in captured.out
    assert (output_dir / "evaluation_manifest.json").exists()


def test_offline_validate_cli_uses_embedded_open_mesh_recipe(
    tmp_path: Path,
    capsys,
) -> None:
    frames_dir = tmp_path / "frames"
    frames_dir.mkdir()
    image = np.full((72, 96), 230, dtype=np.uint8)
    image[22:50:8, 24:72] = 30
    image[22:50, 24:72:8] = 30
    np.save(frames_dir / "frame_000001.npy", image)
    output_dir = tmp_path / "out"
    config_path = tmp_path / "open_mesh.json"
    config_path.write_text(
        json.dumps(
            {
                "target_family": "balloon_envelope",
                "frames_dir": str(frames_dir),
                "output_dir": str(output_dir),
                "fps": 10.0,
                "roi": {
                    "center_x": 48.0,
                    "center_y": 36.0,
                    "width": 60.0,
                    "height": 40.0,
                    "angle_deg": 0.0,
                    "coordinate_space": "acquisition",
                },
                "segmentation": {
                    "polarity": "dark_on_light",
                    "threshold_mode": "fixed",
                    "threshold_value": 160,
                    "blur_kernel": 3,
                    "close_kernel": 5,
                    "open_kernel": 1,
                    "min_component_area_px": 5,
                    "fill_internal_holes": False,
                },
                "detector": {
                    "detector_kind": "balloon_envelope_detector",
                    "envelope_mode": "open_mesh",
                    "contact_source": "bridged_foreground",
                    "min_quality": 0.65,
                    "reject_contact_on_roi_boundary": True,
                    "boundary_margin_px": 4.0,
                    "max_point_jump_px": 25.0,
                    "ignore_internal_texture": True,
                    "fill_internal_holes": False,
                    "bridge_mesh_gaps": True,
                },
            }
        ),
        encoding="utf-8",
    )

    exit_code = main(["--config", str(config_path), "--max-frames", "1"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "evaluation_summary.json" in captured.out
    summary = json.loads((output_dir / "evaluation_summary.json").read_text(encoding="utf-8"))
    assert summary["recipe_snapshot"]["detector"]["envelope_mode"] == "open_mesh"
    assert summary["recipe_snapshot"]["detector"]["contact_source"] == "bridged_foreground"
    assert str(frames_dir) not in json.dumps(summary)
    sample = json.loads(
        (output_dir / "evaluation_samples.jsonl").read_text(encoding="utf-8").splitlines()[0]
    )
    assert sample["diagnostics"]["envelope_mode"] == "open_mesh"
    assert sample["diagnostics"]["contact_source_used"] == "bridged_foreground"
