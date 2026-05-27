from __future__ import annotations

import time
from pathlib import Path

import numpy as np

from yyt1771_af.core.models import Frame
from yyt1771_af.core.statuses import CoordinateSpace


class OfflineFolderCameraSource:
    source_type = "offline"

    def __init__(self, folder: Path) -> None:
        self._folder = folder
        self._files: list[Path] = []
        self._opened = False
        self._index = 0
        self._frame_counter = 0

    def open(self) -> None:
        if not self._folder.exists() or not self._folder.is_dir():
            raise FileNotFoundError(f"offline source folder not found: {self._folder}")
        self._files = _list_frame_files(self._folder)
        if not self._files:
            raise FileNotFoundError(
                "offline source folder must contain at least one .pgm image or .npy frame"
            )
        self._opened = True
        self._index = 0

    def close(self) -> None:
        self._opened = False

    def get_latest_frame(self) -> Frame:
        if not self._opened:
            raise RuntimeError("offline camera source is not opened")

        frame_path = self._files[self._index]
        self._index = (self._index + 1) % len(self._files)
        image = _load_frame(frame_path)
        if image.ndim != 2:
            raise ValueError("offline frames must be 2D grayscale arrays")

        image = np.clip(image, 0, 255).astype(np.uint8)
        self._frame_counter += 1
        return Frame(
            frame_id=self._frame_counter,
            timestamp_ms=time.time_ns() // 1_000_000,
            width=int(image.shape[1]),
            height=int(image.shape[0]),
            coordinate_space=CoordinateSpace.ACQUISITION,
            image=image,
        )


def _list_frame_files(folder: Path) -> list[Path]:
    return sorted(
        path
        for path in folder.iterdir()
        if path.is_file() and path.suffix.lower() in {".pgm", ".npy"}
    )


def _load_frame(path: Path) -> np.ndarray:
    if path.suffix.lower() == ".npy":
        return np.load(path, allow_pickle=False)
    if path.suffix.lower() == ".pgm":
        return _read_pgm(path)
    raise ValueError(f"unsupported offline frame format: {path.suffix}")


def _read_pgm(path: Path) -> np.ndarray:
    data = path.read_bytes()
    position = 0
    magic, position = _read_pgm_token(data, position)
    width_token, position = _read_pgm_token(data, position)
    height_token, position = _read_pgm_token(data, position)
    max_value_token, position = _read_pgm_token(data, position)

    width = int(width_token)
    height = int(height_token)
    max_value = int(max_value_token)
    if width <= 0 or height <= 0:
        raise ValueError("PGM image dimensions must be positive")
    if max_value <= 0 or max_value > 255:
        raise ValueError("PGM max value must be in 1..255")

    if magic == b"P2":
        pixels: list[int] = []
        for _ in range(width * height):
            token, position = _read_pgm_token(data, position)
            pixels.append(int(token))
        return _scale_pgm_pixels(np.asarray(pixels, dtype=np.uint16), max_value).reshape(
            height, width
        )

    if magic == b"P5":
        position = _skip_pgm_whitespace_and_comments(data, position)
        expected_size = width * height
        raster = data[position : position + expected_size]
        if len(raster) != expected_size:
            raise ValueError("PGM binary raster is shorter than declared dimensions")
        return _scale_pgm_pixels(np.frombuffer(raster, dtype=np.uint8), max_value).reshape(
            height, width
        )

    raise ValueError("offline image must be P2 or P5 PGM")


def _scale_pgm_pixels(pixels: np.ndarray, max_value: int) -> np.ndarray:
    if np.any(pixels > max_value):
        raise ValueError("PGM pixel value exceeds max value")
    if max_value == 255:
        return pixels.astype(np.uint8)
    return np.rint(pixels.astype(np.float64) * 255.0 / max_value).astype(np.uint8)


def _read_pgm_token(data: bytes, position: int) -> tuple[bytes, int]:
    position = _skip_pgm_whitespace_and_comments(data, position)
    start = position
    while position < len(data) and not chr(data[position]).isspace():
        if data[position] == ord("#"):
            break
        position += 1
    if start == position:
        raise ValueError("unexpected end of PGM header")
    return data[start:position], position


def _skip_pgm_whitespace_and_comments(data: bytes, position: int) -> int:
    while position < len(data):
        if chr(data[position]).isspace():
            position += 1
            continue
        if data[position] == ord("#"):
            while position < len(data) and data[position] not in {ord("\n"), ord("\r")}:
                position += 1
            continue
        break
    return position
