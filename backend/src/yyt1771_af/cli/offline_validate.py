from __future__ import annotations

import argparse
import os
from collections.abc import Sequence
from pathlib import Path

from pydantic import ValidationError

from yyt1771_af.core.config import load_offline_validation_config
from yyt1771_af.core.statuses import TargetFamily
from yyt1771_af.services.offline_validation_service import (
    OfflineValidationRequest,
    OverlayPolicy,
    run_offline_validation,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    config_path = args.config or args.roi_json
    if config_path is None:
        parser.error("--config or --roi-json is required")
    try:
        config = load_offline_validation_config(Path(config_path))
        frames_dir_value = (
            args.frames_dir or os.environ.get("YYT1771_AF_OFFLINE_DIR") or config.frames_dir
        )
        if not frames_dir_value:
            parser.error("--frames-dir is required when YYT1771_AF_OFFLINE_DIR is not set")
        output_dir_value = args.output_dir or config.output_dir
        if output_dir_value is None:
            parser.error("--output-dir is required when config output_dir is not set")
        target_family = TargetFamily(args.target_family or config.target_family)
        result = run_offline_validation(
            OfflineValidationRequest(
                frames_dir=Path(frames_dir_value),
                target_family=target_family,
                roi=config.roi,
                fps=args.fps or config.fps or 10.0,
                output_dir=Path(output_dir_value),
                max_frames=args.max_frames,
                start_frame=args.start_frame,
                dataset_label=args.dataset_label or config.dataset_label,
                recipe_name=config.recipe_name,
                overlay_policy=OverlayPolicy(
                    first=args.overlay_first,
                    every=args.overlay_every,
                    failures=args.overlay_failures,
                    top_jumps=args.overlay_top_jumps,
                ),
            )
        )
    except (OSError, ValueError, ValidationError) as exc:
        print(f"offline validation failed: {exc}")
        return 2

    print(f"summary: {result.summary_path}")
    print(f"processed_frames: {result.processed_frames}")
    print(f"valid_frames: {result.valid_frames}")
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run offline real-capture detector validation.")
    parser.add_argument("--frames-dir", default=None, help="Offline .npy frame directory.")
    parser.add_argument(
        "--target-family",
        choices=[TargetFamily.BALLOON_ENVELOPE.value, TargetFamily.WIRE_STRIP.value],
        default=None,
    )
    parser.add_argument(
        "--config",
        default=None,
        help="Offline validation JSON/YAML config in acquisition coordinates.",
    )
    parser.add_argument(
        "--roi-json",
        default=None,
        help="Backward-compatible alias for --config.",
    )
    parser.add_argument("--fps", type=float, default=None)
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--max-frames", type=int, default=None)
    parser.add_argument("--start-frame", type=int, default=0)
    parser.add_argument("--dataset-label", default=None)
    parser.add_argument("--overlay-first", type=int, default=0)
    parser.add_argument("--overlay-every", type=int, default=None)
    parser.add_argument("--overlay-failures", action="store_true")
    parser.add_argument("--overlay-top-jumps", type=int, default=0)
    return parser


if __name__ == "__main__":
    raise SystemExit(main())
