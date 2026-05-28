from __future__ import annotations

import csv
import io
import json
import math
import re
import struct
import zipfile
import zlib
from dataclasses import dataclass
from typing import Any
from xml.sax.saxutils import escape

from yyt1771_af.core.path_redaction import sanitize_path_metadata
from yyt1771_af.storage.run_store import RunArtifactStore, run_artifact_store

CSV_COLUMNS = [
    "frame_id",
    "timestamp",
    "temperature_c",
    "detection_status",
    "point_a_x",
    "point_a_y",
    "point_b_x",
    "point_b_y",
    "distance_px",
    "quality",
    "reason",
]

WINDOWS_INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\s]+')


@dataclass(frozen=True, slots=True)
class ExportPayload:
    content: bytes
    media_type: str
    filename: str


class ExportService:
    def __init__(self, *, store: RunArtifactStore) -> None:
        self._store = store

    def export_csv(self, run_id: str) -> ExportPayload:
        artifacts = self._artifacts(run_id)
        text = _csv_text(artifacts["samples"])
        return ExportPayload(
            content=text.encode("utf-8"),
            media_type="text/csv; charset=utf-8",
            filename=_safe_export_filename(run_id, "csv"),
        )

    def export_json(self, run_id: str) -> ExportPayload:
        artifacts = self._artifacts(run_id)
        measurement_definition = artifacts["measurement_definition"]
        payload = {
            "run_metadata": _sanitize_export_metadata(artifacts["run_metadata"]),
            "measurement_definition": measurement_definition,
            "samples": artifacts["samples"],
            "analysis_result": artifacts["analysis_result"],
            "detector_version": _detector_version(measurement_definition, artifacts["samples"]),
            "recipe": _recipe_payload(measurement_definition),
        }
        return ExportPayload(
            content=json.dumps(payload, indent=2, sort_keys=True).encode("utf-8"),
            media_type="application/json",
            filename=_safe_export_filename(run_id, "json"),
        )

    def export_png(self, run_id: str) -> ExportPayload:
        artifacts = self._artifacts(run_id)
        content = _png_chart(artifacts["analysis_result"])
        return ExportPayload(
            content=content,
            media_type="image/png",
            filename=_safe_export_filename(run_id, "png"),
        )

    def export_xlsx(self, run_id: str) -> ExportPayload:
        artifacts = self._artifacts(run_id)
        content = _xlsx_workbook(_sanitize_export_artifacts(artifacts))
        return ExportPayload(
            content=content,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename=_safe_export_filename(run_id, "xlsx"),
        )

    def _artifacts(self, run_id: str) -> dict[str, Any]:
        samples = self._store.read_samples(run_id)
        run_metadata = self._store.read_metadata(run_id)
        measurement_definition = self._store.read_measurement_definition(run_id)
        analysis_result = self._store.read_analysis(run_id)
        if run_metadata is None and not samples and measurement_definition is None:
            raise KeyError(f"run {run_id} is not available")
        return {
            "run_metadata": run_metadata,
            "measurement_definition": measurement_definition,
            "samples": samples,
            "analysis_result": analysis_result,
        }


def _csv_text(samples: list[dict[str, Any]]) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=CSV_COLUMNS)
    writer.writeheader()
    for sample in samples:
        writer.writerow(_csv_row(sample))
    return output.getvalue()


def _csv_row(sample: dict[str, Any]) -> dict[str, Any]:
    detection = sample.get("detection") or {}
    point_a = detection.get("point_a") or {}
    point_b = detection.get("point_b") or {}
    frame_ref = detection.get("frame_ref") or {}
    diagnostics = detection.get("diagnostics") or {}
    status = detection.get("status")
    reason = diagnostics.get("message") or (status if status != "ok" else "")
    return {
        "frame_id": _blank_none(frame_ref.get("frame_id")),
        "timestamp": _blank_none(sample.get("timestamp_ms")),
        "temperature_c": _blank_none(sample.get("temperature_c")),
        "detection_status": _blank_none(status),
        "point_a_x": _blank_none(point_a.get("x")),
        "point_a_y": _blank_none(point_a.get("y")),
        "point_b_x": _blank_none(point_b.get("x")),
        "point_b_y": _blank_none(point_b.get("y")),
        "distance_px": _blank_none(detection.get("distance_px")),
        "quality": _blank_none(detection.get("quality")),
        "reason": _blank_none(reason),
    }


def _blank_none(value: Any) -> Any:
    return "" if value is None else value


def _detector_version(
    measurement_definition: dict[str, Any] | None,
    samples: list[dict[str, Any]],
) -> str | None:
    if measurement_definition is not None:
        version = measurement_definition.get("detector_version")
        if version is not None:
            return str(version)
    for sample in samples:
        diagnostics = (sample.get("detection") or {}).get("diagnostics") or {}
        version = diagnostics.get("detector_version")
        if version is not None:
            return str(version)
    return None


def _recipe_payload(measurement_definition: dict[str, Any] | None) -> dict[str, Any] | None:
    if measurement_definition is None:
        return None
    return {
        "name": measurement_definition.get("recipe_name"),
        "target_family": measurement_definition.get("target_family"),
        "roi": measurement_definition.get("roi"),
        "detector_version": measurement_definition.get("detector_version"),
    }


def _safe_export_filename(run_id: str, extension: str) -> str:
    safe_stem = WINDOWS_INVALID_FILENAME_CHARS.sub("_", run_id).strip("._")
    if not safe_stem:
        safe_stem = "run"
    return f"{safe_stem}_export.{extension}"


def _sanitize_export_artifacts(artifacts: dict[str, Any]) -> dict[str, Any]:
    return artifacts | {
        "run_metadata": _sanitize_export_metadata(artifacts.get("run_metadata")),
    }


def _sanitize_export_metadata(value: Any, *, key: str | None = None) -> Any:
    return sanitize_path_metadata(value, key=key)


def _png_chart(analysis: dict[str, Any] | None) -> bytes:
    width = 900
    height = 520
    pixels = bytearray([255, 255, 255] * width * height)

    _draw_line(pixels, width, 70, 48, 70, 430, (120, 133, 148))
    _draw_line(pixels, width, 70, 430, 820, 430, (120, 133, 148))
    _draw_text(pixels, width, 70, 20, "temperature-distance curve", (36, 49, 61))

    if analysis is None:
        _draw_text(pixels, width, 70, 82, "analysis status: missing", (180, 35, 24))
        return _encode_png(width, height, pixels)

    status = str(analysis.get("status", "unknown"))
    curve = analysis.get("curve") or []
    result = analysis.get("result") or {}
    _draw_text(pixels, width, 70, 82, f"analysis status: {status}", (36, 49, 61))
    invalid_count = result.get("invalid_sample_count")
    if invalid_count is not None:
        _draw_text(pixels, width, 70, 106, f"invalid samples: {invalid_count}", (36, 49, 61))

    af95 = result.get("af95_temperature_c")
    if af95 is not None:
        _draw_text(pixels, width, 70, 130, f"Af-95: {af95:.2f} C", (15, 118, 110))

    points = [
        (float(point["temperature_c"]), float(point["distance_px"]))
        for point in curve
        if point.get("temperature_c") is not None and point.get("distance_px") is not None
    ]
    if not points:
        return _encode_png(width, height, pixels)

    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    chart_left, chart_top, chart_right, chart_bottom = 70, 170, 820, 430
    mapped = [
        (
            _map_value(x, min_x, max_x, chart_left, chart_right),
            _map_value(y, min_y, max_y, chart_bottom, chart_top),
        )
        for x, y in points
    ]
    for start, end in zip(mapped, mapped[1:], strict=False):
        _draw_line(pixels, width, start[0], start[1], end[0], end[1], (15, 118, 110), thickness=3)
    for x, y in mapped:
        _draw_rect(pixels, width, x - 3, y - 3, x + 3, y + 3, (180, 83, 9))

    if af95 is not None and min_x <= af95 <= max_x:
        af_x = _map_value(float(af95), min_x, max_x, chart_left, chart_right)
        _draw_line(pixels, width, af_x, chart_top, af_x, chart_bottom, (180, 35, 24), thickness=2)

    return _encode_png(width, height, pixels)


def _map_value(value: float, min_value: float, max_value: float, out_min: int, out_max: int) -> int:
    if abs(max_value - min_value) < 1e-9:
        return (out_min + out_max) // 2
    fraction = (value - min_value) / (max_value - min_value)
    return int(round(out_min + fraction * (out_max - out_min)))


def _draw_line(
    pixels: bytearray,
    width: int,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    color: tuple[int, int, int],
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
        _draw_rect(pixels, width, x0 - half, y0 - half, x0 + half, y0 + half, color)
        if x0 == x1 and y0 == y1:
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x0 += sx
        if e2 <= dx:
            err += dx
            y0 += sy


def _draw_rect(
    pixels: bytearray,
    width: int,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    color: tuple[int, int, int],
) -> None:
    height = len(pixels) // (width * 3)
    for y in range(max(0, y0), min(height, y1 + 1)):
        for x in range(max(0, x0), min(width, x1 + 1)):
            offset = (y * width + x) * 3
            pixels[offset : offset + 3] = bytes(color)


def _draw_text(
    pixels: bytearray,
    width: int,
    x: int,
    y: int,
    text: str,
    color: tuple[int, int, int],
) -> None:
    cursor = x
    for char in text.lower():
        if char == " ":
            cursor += 8
            continue
        code = ord(char)
        for bit in range(7):
            if code & (1 << bit):
                row = bit
                _draw_rect(pixels, width, cursor, y + row * 2, cursor + 5, y + row * 2 + 1, color)
        cursor += 8


def _encode_png(width: int, height: int, pixels: bytearray) -> bytes:
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


def _xlsx_workbook(artifacts: dict[str, Any]) -> bytes:
    sample_rows = [
        [_csv_row(sample)[column] for column in CSV_COLUMNS] for sample in artifacts["samples"]
    ]
    sheets = [
        ("Summary", _summary_rows(artifacts)),
        ("Samples", [CSV_COLUMNS] + sample_rows),
        ("Analysis", _analysis_rows(artifacts.get("analysis_result"))),
        ("Metadata", _metadata_rows(artifacts)),
    ]
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as workbook:
        workbook.writestr("[Content_Types].xml", _xlsx_content_types(len(sheets)))
        workbook.writestr("_rels/.rels", _xlsx_root_rels())
        workbook.writestr("xl/_rels/workbook.xml.rels", _xlsx_workbook_rels(len(sheets)))
        workbook.writestr("xl/workbook.xml", _xlsx_workbook_xml([name for name, _ in sheets]))
        for index, (_, rows) in enumerate(sheets, start=1):
            workbook.writestr(f"xl/worksheets/sheet{index}.xml", _xlsx_sheet(rows))
    return output.getvalue()


def _summary_rows(artifacts: dict[str, Any]) -> list[list[Any]]:
    metadata = artifacts.get("run_metadata") or {}
    analysis = artifacts.get("analysis_result") or {}
    result = analysis.get("result") or {}
    return [
        ["Field", "Value"],
        ["run_id", metadata.get("run_id", "")],
        ["analysis_status", analysis.get("status", "")],
        ["af95_temperature_c", result.get("af95_temperature_c", "")],
        ["valid_sample_count", result.get("valid_sample_count", "")],
        ["invalid_sample_count", result.get("invalid_sample_count", "")],
    ]


def _analysis_rows(analysis: dict[str, Any] | None) -> list[list[Any]]:
    if analysis is None:
        return [["Field", "Value"], ["status", "missing"]]
    result = analysis.get("result") or {}
    rows = [
        ["Field", "Value"],
        ["method", analysis.get("method", "")],
        ["status", analysis.get("status", "")],
    ]
    for key, value in result.items():
        rows.append([key, json.dumps(value) if isinstance(value, list) else value])
    rows.append([])
    rows.append(
        ["sample_index", "timestamp_ms", "temperature_c", "distance_px", "recovered_fraction"]
    )
    for point in analysis.get("curve") or []:
        rows.append(
            [
                point.get("sample_index", ""),
                point.get("timestamp_ms", ""),
                point.get("temperature_c", ""),
                point.get("distance_px", ""),
                point.get("recovered_fraction", ""),
            ]
        )
    return rows


def _metadata_rows(artifacts: dict[str, Any]) -> list[list[Any]]:
    return [
        ["Section", "JSON"],
        ["run_metadata", json.dumps(artifacts.get("run_metadata"), sort_keys=True)],
        [
            "measurement_definition",
            json.dumps(artifacts.get("measurement_definition"), sort_keys=True),
        ],
        [
            "recipe",
            json.dumps(
                _recipe_payload(artifacts.get("measurement_definition")),
                sort_keys=True,
            ),
        ],
    ]


def _xlsx_content_types(sheet_count: int) -> str:
    sheet_overrides = "".join(
        f'<Override PartName="/xl/worksheets/sheet{index}.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        for index in range(1, sheet_count + 1)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" '
        'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        f"{sheet_overrides}</Types>"
    )


def _xlsx_root_rels() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="xl/workbook.xml"/></Relationships>'
    )


def _xlsx_workbook_rels(sheet_count: int) -> str:
    relationships = "".join(
        f'<Relationship Id="rId{index}" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        f'Target="worksheets/sheet{index}.xml"/>'
        for index in range(1, sheet_count + 1)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        f"{relationships}</Relationships>"
    )


def _xlsx_workbook_xml(sheet_names: list[str]) -> str:
    sheets = "".join(
        f'<sheet name="{escape(name)}" sheetId="{index}" r:id="rId{index}"/>'
        for index, name in enumerate(sheet_names, start=1)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f"<sheets>{sheets}</sheets></workbook>"
    )


def _xlsx_sheet(rows: list[list[Any]]) -> str:
    xml_rows = []
    for row_index, row in enumerate(rows, start=1):
        cells = []
        for column_index, value in enumerate(row, start=1):
            cell_ref = f"{_xlsx_column_name(column_index)}{row_index}"
            is_number = (
                isinstance(value, int | float)
                and not isinstance(value, bool)
                and math.isfinite(value)
            )
            if is_number:
                cells.append(f'<c r="{cell_ref}"><v>{value}</v></c>')
            else:
                text = escape(str(_blank_none(value)))
                cells.append(f'<c r="{cell_ref}" t="inlineStr"><is><t>{text}</t></is></c>')
        xml_rows.append(f'<row r="{row_index}">{"".join(cells)}</row>')
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f"<sheetData>{''.join(xml_rows)}</sheetData></worksheet>"
    )


def _xlsx_column_name(index: int) -> str:
    name = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        name = chr(ord("A") + remainder) + name
    return name


export_service = ExportService(store=run_artifact_store)
