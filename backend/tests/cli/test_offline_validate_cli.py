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
