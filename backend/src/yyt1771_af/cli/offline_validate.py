from __future__ import annotations

import argparse
import os
from collections.abc import Sequence
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError

from yyt1771_af.core.models import RotatedRoi
from yyt1771_af.core.statuses import TargetFamily
from yyt1771_af.services.offline_validation_service import (
    OfflineValidationRequest,
    OverlayPolicy,
    run_offline_validation,
)


class RoiJsonPayload(BaseModel):
    target_family: TargetFamily | None = None
    roi: RotatedRoi
    recipe: dict[str, object] = Field(default_factory=dict)


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    frames_dir_value = args.frames_dir or os.environ.get("YYT1771_AF_OFFLINE_DIR")
    if not frames_dir_value:
        parser.error("--frames-dir is required when YYT1771_AF_OFFLINE_DIR is not set")
    try:
        roi_payload = _load_roi_payload(Path(args.roi_json))
        target_family = TargetFamily(args.target_family or roi_payload.target_family)
        result = run_offline_validation(
            OfflineValidationRequest(
                frames_dir=Path(frames_dir_value),
                target_family=target_family,
                roi=roi_payload.roi,
                fps=args.fps,
                output_dir=Path(args.output_dir),
                max_frames=args.max_frames,
                start_frame=args.start_frame,
                dataset_label=args.dataset_label,
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
    parser.add_argument("--roi-json", required=True, help="ROI JSON in acquisition coordinates.")
    parser.add_argument("--fps", type=float, default=10.0)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--max-frames", type=int, default=None)
    parser.add_argument("--start-frame", type=int, default=0)
    parser.add_argument("--dataset-label", default=None)
    parser.add_argument("--overlay-first", type=int, default=0)
    parser.add_argument("--overlay-every", type=int, default=None)
    parser.add_argument("--overlay-failures", action="store_true")
    parser.add_argument("--overlay-top-jumps", type=int, default=0)
    return parser


def _load_roi_payload(path: Path) -> RoiJsonPayload:
    payload = RoiJsonPayload.model_validate_json(path.read_text(encoding="utf-8"))
    if payload.target_family is None:
        raise ValueError("roi-json must include target_family when --target-family is omitted")
    return payload


if __name__ == "__main__":
    raise SystemExit(main())
