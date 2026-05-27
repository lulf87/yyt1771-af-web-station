from __future__ import annotations

from typing import Protocol

from yyt1771_af.core.models import Frame


class CameraSource(Protocol):
    def open(self) -> None: ...

    def close(self) -> None: ...

    def get_latest_frame(self) -> Frame: ...
