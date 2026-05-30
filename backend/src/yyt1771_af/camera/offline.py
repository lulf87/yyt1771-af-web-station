from __future__ import annotations

import re
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from yyt1771_af.core.models import Frame
from yyt1771_af.core.statuses import CoordinateSpace


class EndOfOfflineStreamError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class OfflineFrameInfo:
    frame_name: str
    frame_index: int
    width: int
    height: int
    dtype: str
    nbytes: int


class OfflineFolderCameraSource:
    source_type = "offline"

    def __init__(self, folder: Path, *, loop: bool = False) -> None:
        self._folder = folder
        self._files: list[Path] = []
        self._opened = False
        self._index = 0
        self._frame_counter = 0
        self._loop = loop

    def open(self) -> None:
        if not self._folder.exists() or not self._folder.is_dir():
            raise FileNotFoundError(f"offline source folder not found: {self._folder}")
        self._files = list_offline_frame_files(self._folder)
        if not self._files:
            raise FileNotFoundError(
                "offline source folder must contain at least one .pgm image or .npy frame"
            )
        self._opened = True
        self._index = 0

    def close(self) -> None:
        self._opened = False

    @property
    def frame_count(self) -> int:
        return len(self._files)

    @property
    def cached_image_count(self) -> int:
        return 0

    @property
    def frame_names(self) -> list[str]:
        return [path.name for path in self._files]

    @property
    def frame_paths(self) -> list[Path]:
        return list(self._files)

    def peek_frame(self) -> Frame:
        if not self._opened:
            raise RuntimeError("offline camera source is not opened")
        if not self._files:
            raise EndOfOfflineStreamError("offline source has no frames")
        return self._frame_from_path(self._files[0], frame_index=0, advance_counter=False)

    def read_frame(self, frame_index: int) -> Frame:
        if not self._opened:
            raise RuntimeError("offline camera source is not opened")
        if frame_index < 0 or frame_index >= len(self._files):
            raise IndexError("offline frame index is outside available frames")
        return self._frame_from_path(
            self._files[frame_index],
            frame_index=frame_index,
            advance_counter=False,
            frame_id=frame_index + 1,
        )

    def frame_info(self, frame_index: int) -> OfflineFrameInfo:
        if frame_index < 0 or frame_index >= len(self._files):
            raise IndexError("offline frame index is outside available frames")
        path = self._files[frame_index]
        image = _load_frame(path, mmap_mode="r")
        _require_grayscale(image, path)
        return OfflineFrameInfo(
            frame_name=path.name,
            frame_index=frame_index,
            width=int(image.shape[1]),
            height=int(image.shape[0]),
            dtype=str(image.dtype),
            nbytes=int(image.nbytes),
        )

    def get_latest_frame(self) -> Frame:
        if not self._opened:
            raise RuntimeError("offline camera source is not opened")
        if self._index >= len(self._files):
            if not self._loop:
                raise EndOfOfflineStreamError("offline source reached end of stream")
            self._index = 0

        frame_path = self._files[self._index]
        frame_index = self._index
        self._index += 1
        return self._frame_from_path(frame_path, frame_index=frame_index, advance_counter=True)

    def _frame_from_path(
        self,
        path: Path,
        *,
        frame_index: int,
        advance_counter: bool,
        frame_id: int | None = None,
    ) -> Frame:
        image = _load_frame(path)
        _require_grayscale(image, path)
        image = np.clip(np.asarray(image), 0, 255).astype(np.uint8, copy=False)
        if frame_id is not None:
            resolved_frame_id = frame_id
        elif advance_counter:
            self._frame_counter += 1
            resolved_frame_id = self._frame_counter
        else:
            resolved_frame_id = self._frame_counter + 1
        return Frame(
            frame_id=resolved_frame_id,
            timestamp_ms=time.time_ns() // 1_000_000,
            width=int(image.shape[1]),
            height=int(image.shape[0]),
            coordinate_space=CoordinateSpace.ACQUISITION,
            image=image,
            frame_name=path.name,
            frame_index=frame_index,
            dtype=str(image.dtype),
        )


def list_offline_frame_files(folder: Path) -> list[Path]:
    return sorted(
        (
            path
            for path in folder.iterdir()
            if path.is_file() and path.suffix.lower() in {".pgm", ".npy"}
        ),
        key=_natural_sort_key,
    )


def _natural_sort_key(path: Path) -> tuple[object, ...]:
    parts = re.split(r"(\d+)", path.name)
    key: list[object] = []
    for part in parts:
        if part.isdigit():
            key.append(int(part))
        else:
            key.append(part.lower())
    return tuple(key)


def parsed_frame_index(path: Path) -> int | None:
    matches = re.findall(r"\d+", path.stem)
    if not matches:
        return None
    return int(matches[-1])


def _load_frame(path: Path, *, mmap_mode: str | None = None) -> np.ndarray:
    if path.suffix.lower() == ".npy":
        return np.load(path, allow_pickle=False, mmap_mode=mmap_mode)
    if mmap_mode is not None:
        raise ValueError("mmap metadata loading is only supported for .npy frames")
    if path.suffix.lower() == ".pgm":
        return _read_pgm(path)
    raise ValueError(f"unsupported offline frame format: {path.suffix}")


def load_offline_frame(path: Path) -> np.ndarray:
    image = _load_frame(path)
    _require_grayscale(image, path)
    return np.clip(np.asarray(image), 0, 255).astype(np.uint8, copy=False)


def load_offline_frame_info(path: Path, *, frame_index: int) -> OfflineFrameInfo:
    image = _load_frame(path, mmap_mode="r")
    _require_grayscale(image, path)
    return OfflineFrameInfo(
        frame_name=path.name,
        frame_index=frame_index,
        width=int(image.shape[1]),
        height=int(image.shape[0]),
        dtype=str(image.dtype),
        nbytes=int(image.nbytes),
    )


def _require_grayscale(image: np.ndarray, path: Path) -> None:
    if image.ndim != 2:
        raise ValueError(
            f"offline frame {path.name} has unsupported shape {image.shape}; "
            "expected a 2D grayscale frame"
        )


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
