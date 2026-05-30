"""Debug-level control for detector diagnostic cost.

The formal detection contract (status, ``point_a``/``point_b``, ``distance_px``)
is identical at every debug level. ``debug_level`` only controls how much
optional diagnostic data the detector computes:

- ``full``  - all diagnostics, including the wire rejected-interval analysis and
  the lazily-attached raw/bridged/virtual-envelope intervals. Used by Setup and
  single-frame inspection.
- ``basic`` - formal A/B + ROI + the core diagnostics only; the heavy diagnostic
  passes above are skipped. Used by Live Offline Run playback to hit ~10Hz.
- ``none``  - same skip set as ``basic`` (reserved for callers that want the
  lightest payload).

This is a pure typing/utility module: no FastAPI, hardware, or filesystem
dependencies.
"""

from __future__ import annotations

from typing import Literal

DebugLevel = Literal["none", "basic", "full"]

DEFAULT_DEBUG_LEVEL: DebugLevel = "full"


def wants_full_diagnostics(debug_level: DebugLevel) -> bool:
    """Return True only for the ``full`` level (heavy diagnostics enabled)."""
    return debug_level == "full"
