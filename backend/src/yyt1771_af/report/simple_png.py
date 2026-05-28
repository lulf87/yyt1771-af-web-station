from __future__ import annotations

import struct
import zlib
from collections.abc import Iterable

import numpy as np

Color = tuple[int, int, int]

FONT_5X7: dict[str, tuple[str, ...]] = {
    " ": ("00000", "00000", "00000", "00000", "00000", "00000", "00000"),
    "-": ("00000", "00000", "00000", "11111", "00000", "00000", "00000"),
    ".": ("00000", "00000", "00000", "00000", "00000", "01100", "01100"),
    ":": ("00000", "01100", "01100", "00000", "01100", "01100", "00000"),
    "_": ("00000", "00000", "00000", "00000", "00000", "00000", "11111"),
    "/": ("00001", "00010", "00100", "01000", "10000", "00000", "00000"),
    "0": ("01110", "10001", "10011", "10101", "11001", "10001", "01110"),
    "1": ("00100", "01100", "00100", "00100", "00100", "00100", "01110"),
    "2": ("01110", "10001", "00001", "00010", "00100", "01000", "11111"),
    "3": ("11110", "00001", "00001", "01110", "00001", "00001", "11110"),
    "4": ("00010", "00110", "01010", "10010", "11111", "00010", "00010"),
    "5": ("11111", "10000", "10000", "11110", "00001", "00001", "11110"),
    "6": ("01110", "10000", "10000", "11110", "10001", "10001", "01110"),
    "7": ("11111", "00001", "00010", "00100", "01000", "01000", "01000"),
    "8": ("01110", "10001", "10001", "01110", "10001", "10001", "01110"),
    "9": ("01110", "10001", "10001", "01111", "00001", "00001", "01110"),
    "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    "B": ("11110", "10001", "10001", "11110", "10001", "10001", "11110"),
    "C": ("01111", "10000", "10000", "10000", "10000", "10000", "01111"),
    "D": ("11110", "10001", "10001", "10001", "10001", "10001", "11110"),
    "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    "F": ("11111", "10000", "10000", "11110", "10000", "10000", "10000"),
    "G": ("01111", "10000", "10000", "10011", "10001", "10001", "01110"),
    "H": ("10001", "10001", "10001", "11111", "10001", "10001", "10001"),
    "I": ("01110", "00100", "00100", "00100", "00100", "00100", "01110"),
    "J": ("00111", "00010", "00010", "00010", "00010", "10010", "01100"),
    "K": ("10001", "10010", "10100", "11000", "10100", "10010", "10001"),
    "L": ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    "M": ("10001", "11011", "10101", "10101", "10001", "10001", "10001"),
    "N": ("10001", "11001", "10101", "10011", "10001", "10001", "10001"),
    "O": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    "P": ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    "Q": ("01110", "10001", "10001", "10001", "10101", "10010", "01101"),
    "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    "S": ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    "T": ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    "U": ("10001", "10001", "10001", "10001", "10001", "10001", "01110"),
    "V": ("10001", "10001", "10001", "10001", "10001", "01010", "00100"),
    "W": ("10001", "10001", "10001", "10101", "10101", "10101", "01010"),
    "X": ("10001", "10001", "01010", "00100", "01010", "10001", "10001"),
    "Y": ("10001", "10001", "01010", "00100", "00100", "00100", "00100"),
    "Z": ("11111", "00001", "00010", "00100", "01000", "10000", "11111"),
}


def blank_rgb(width: int, height: int, color: Color = (255, 255, 255)) -> bytearray:
    return bytearray(color * (width * height))


def grayscale_to_rgb(image: np.ndarray) -> bytearray:
    source = np.clip(np.asarray(image), 0, 255).astype(np.uint8, copy=False)
    rgb = np.repeat(source[:, :, None], 3, axis=2)
    return bytearray(rgb.tobytes())


def draw_rect(
    pixels: bytearray,
    width: int,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    color: Color,
) -> None:
    height = len(pixels) // (width * 3)
    for y in range(max(0, y0), min(height, y1 + 1)):
        for x in range(max(0, x0), min(width, x1 + 1)):
            offset = (y * width + x) * 3
            pixels[offset : offset + 3] = bytes(color)


def draw_line(
    pixels: bytearray,
    width: int,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    color: Color,
    *,
    thickness: int = 1,
) -> None:
    dx = abs(x1 - x0)
    sx = 1 if x0 < x1 else -1
    dy = -abs(y1 - y0)
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    while True:
        half = thickness // 2
        draw_rect(pixels, width, x0 - half, y0 - half, x0 + half, y0 + half, color)
        if x0 == x1 and y0 == y1:
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x0 += sx
        if e2 <= dx:
            err += dx
            y0 += sy


def draw_circle(
    pixels: bytearray,
    width: int,
    cx: int,
    cy: int,
    radius: int,
    color: Color,
) -> None:
    for y in range(cy - radius, cy + radius + 1):
        for x in range(cx - radius, cx + radius + 1):
            if (x - cx) ** 2 + (y - cy) ** 2 <= radius**2:
                draw_rect(pixels, width, x, y, x, y, color)


def draw_polyline(
    pixels: bytearray,
    width: int,
    points: Iterable[tuple[int, int]],
    color: Color,
    *,
    thickness: int = 1,
) -> None:
    point_list = list(points)
    for start, end in zip(point_list, point_list[1:], strict=False):
        draw_line(pixels, width, start[0], start[1], end[0], end[1], color, thickness=thickness)


def draw_text(
    pixels: bytearray,
    width: int,
    x: int,
    y: int,
    text: str,
    color: Color,
    *,
    scale: int = 1,
) -> None:
    cursor_x = x
    for char in text.upper():
        glyph = FONT_5X7.get(char, FONT_5X7[" "])
        for row_index, row in enumerate(glyph):
            for column_index, bit in enumerate(row):
                if bit == "1":
                    draw_rect(
                        pixels,
                        width,
                        cursor_x + column_index * scale,
                        y + row_index * scale,
                        cursor_x + (column_index + 1) * scale - 1,
                        y + (row_index + 1) * scale - 1,
                        color,
                    )
        cursor_x += 6 * scale


def encode_png(width: int, height: int, pixels: bytearray) -> bytes:
    raw_rows = bytearray()
    row_length = width * 3
    for y in range(height):
        raw_rows.append(0)
        start = y * row_length
        raw_rows.extend(pixels[start : start + row_length])
    return (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + _png_chunk(b"IDAT", zlib.compress(bytes(raw_rows), level=9))
        + _png_chunk(b"IEND", b"")
    )


def _png_chunk(kind: bytes, data: bytes) -> bytes:
    checksum = zlib.crc32(kind)
    checksum = zlib.crc32(data, checksum) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", checksum)
