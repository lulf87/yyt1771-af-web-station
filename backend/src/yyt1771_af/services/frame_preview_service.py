from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from pydantic import BaseModel, Field

from yyt1771_af.core.models import Frame
from yyt1771_af.core.statuses import CoordinateSpace
from yyt1771_af.report.simple_png import encode_png, grayscale_to_rgb


class FramePreviewMetadata(BaseModel):
    frame_id: int | None = None
    frame_index: int | None = None
    frame_name: str | None = None
    acquisition_width: int = Field(gt=0)
    acquisition_height: int = Field(gt=0)
    display_width: int = Field(gt=0)
    display_height: int = Field(gt=0)
    scale_x: float = Field(gt=0.0)
    scale_y: float = Field(gt=0.0)
    coordinate_space: CoordinateSpace = CoordinateSpace.ACQUISITION
    preview_url: str


@dataclass(frozen=True, slots=True)
class FramePreviewPng:
    metadata: FramePreviewMetadata
    png: bytes


def build_frame_preview_metadata(
    *,
    frame_id: int | None,
    frame_index: int | None,
    frame_name: str | None,
    acquisition_width: int,
    acquisition_height: int,
    preview_url: str,
    max_width: int,
    max_height: int | None = None,
) -> FramePreviewMetadata:
    display_width, display_height = preview_size(
        acquisition_width=acquisition_width,
        acquisition_height=acquisition_height,
        max_width=max_width,
        max_height=max_height,
    )
    return FramePreviewMetadata(
        frame_id=frame_id,
        frame_index=frame_index,
        frame_name=frame_name,
        acquisition_width=acquisition_width,
        acquisition_height=acquisition_height,
        display_width=display_width,
        display_height=display_height,
        scale_x=round(display_width / acquisition_width, 8),
        scale_y=round(display_height / acquisition_height, 8),
        coordinate_space=CoordinateSpace.ACQUISITION,
        preview_url=preview_url,
    )


def build_frame_preview_png(
    *,
    frame: Frame,
    preview_url: str,
    max_width: int,
    max_height: int | None = None,
    compression_level: int = 9,
) -> FramePreviewPng:
    preview_image = downsample_grayscale(
        frame.image,
        max_width=max_width,
        max_height=max_height,
    )
    height, width = preview_image.shape
    metadata = FramePreviewMetadata(
        frame_id=frame.frame_id,
        frame_index=frame.frame_index,
        frame_name=frame.frame_name,
        acquisition_width=frame.width,
        acquisition_height=frame.height,
        display_width=width,
        display_height=height,
        scale_x=round(width / frame.width, 8),
        scale_y=round(height / frame.height, 8),
        coordinate_space=CoordinateSpace.ACQUISITION,
        preview_url=preview_url,
    )
    return FramePreviewPng(
        metadata=metadata,
        png=encode_png(
            width,
            height,
            grayscale_to_rgb(preview_image),
            compression_level=compression_level,
        ),
    )


def preview_size(
    *,
    acquisition_width: int,
    acquisition_height: int,
    max_width: int,
    max_height: int | None = None,
) -> tuple[int, int]:
    if max_width <= 0:
        raise ValueError("max_width must be positive")
    if max_height is not None and max_height <= 0:
        raise ValueError("max_height must be positive")
    scale = min(1.0, max_width / acquisition_width)
    if max_height is not None:
        scale = min(scale, max_height / acquisition_height)
    display_width = max(1, int(round(acquisition_width * scale)))
    display_height = max(1, int(round(acquisition_height * scale)))
    return display_width, display_height


def downsample_grayscale(
    image: np.ndarray,
    *,
    max_width: int,
    max_height: int | None = None,
) -> np.ndarray:
    source = np.asarray(image)
    if source.ndim != 2:
        raise ValueError(f"preview requires a 2D grayscale frame, got shape {source.shape}")
    acquisition_height, acquisition_width = source.shape
    display_width, display_height = preview_size(
        acquisition_width=acquisition_width,
        acquisition_height=acquisition_height,
        max_width=max_width,
        max_height=max_height,
    )
    if display_width == acquisition_width and display_height == acquisition_height:
        return np.clip(source, 0, 255).astype(np.uint8, copy=False)
    y_indices = np.linspace(0, acquisition_height - 1, display_height).astype(np.int64)
    x_indices = np.linspace(0, acquisition_width - 1, display_width).astype(np.int64)
    downsampled = source[np.ix_(y_indices, x_indices)]
    return np.clip(downsampled, 0, 255).astype(np.uint8, copy=False)
