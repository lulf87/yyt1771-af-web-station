from __future__ import annotations

import numpy as np
from yyt1771_af.core.models import Point2D, RotatedRoi
from yyt1771_af.report.debug_overlay import render_debug_overlay_png


def test_debug_overlay_renders_png_without_recomputing_points() -> None:
    frame = np.full((40, 60), 220, dtype=np.uint8)
    frame[18:23, 10:50] = 30
    roi = RotatedRoi(center_x=30.0, center_y=20.0, width=44.0, height=16.0, angle_deg=0.0)
    point_a = Point2D(x=10.0, y=20.0)
    point_b = Point2D(x=50.0, y=20.0)

    payload = render_debug_overlay_png(
        frame=frame,
        roi=roi,
        point_a=point_a,
        point_b=point_b,
        frame_index=7,
        status="ok",
        distance_px=40.0,
        quality=0.91,
        reason=None,
    )

    assert payload.startswith(b"\x89PNG\r\n\x1a\n")
    assert b"IEND" in payload[-32:]
