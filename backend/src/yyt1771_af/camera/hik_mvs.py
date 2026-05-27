from __future__ import annotations


class HikMvsCameraSource:
    def __init__(self) -> None:
        self._sdk = None

    def _load_sdk(self) -> None:
        raise NotImplementedError("Hik MVS SDK loading is intentionally deferred.")

    def open(self) -> None:
        self._load_sdk()

    def close(self) -> None:
        self._sdk = None
