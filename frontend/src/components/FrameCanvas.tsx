import { useRef, useState } from "react";
import type { PointerEvent } from "react";

import type { FrameRef, Point2D, RotatedRoi, SetupDetectResponse } from "../api/types";
import {
  clientPointToAcquisition,
  createRoiFromDrag,
  hitTestRoiHandle,
  hitTestRoiRotationHandle,
  moveRoiByDelta,
  pointInsideRoi,
  pointToOverlayCircle,
  resizeRoiFromHandle,
  roiRotationHandlePoint,
  roiHandlePoints,
  roiToOverlayRect,
  rotateRoiFromPointer,
  type RoiHandle,
} from "../geometry/transforms";

interface FrameCanvasProps {
  frameRef: FrameRef | null;
  previewUrl: string | null;
  roi: RotatedRoi;
  detection: SetupDetectResponse | null;
  interactive?: boolean;
  onRoiChange?: (roi: RotatedRoi) => void;
  onPreviewError?: (previewUrl: string) => void;
  onPreviewLoad?: (previewUrl: string) => void;
  emptyLabel?: string;
  showDiagnosticsOverlay?: boolean;
  rawOnly?: boolean;
  probeMode?: boolean;
  onProbePoint?: (point: Point2D) => void;
}

type DragState =
  | {
      mode: "create";
      start: Point2D;
    }
  | {
      mode: "move";
      last: Point2D;
    }
  | {
      mode: "resize";
      handle: RoiHandle;
    }
  | {
      mode: "rotate";
    };

export function FrameCanvas({
  frameRef,
  previewUrl,
  roi,
  detection,
  interactive = false,
  onRoiChange,
  onPreviewError,
  onPreviewLoad,
  emptyLabel = "No frozen frame",
  showDiagnosticsOverlay = false,
  rawOnly = false,
  probeMode = false,
  onProbePoint,
}: FrameCanvasProps) {
  const svgRef = useRef<SVGSVGElement | null>(null);
  const [dragState, setDragState] = useState<DragState | null>(null);

  if (frameRef === null || previewUrl === null) {
    return (
      <div className="frame-empty" role="img" aria-label="No frozen frame">
        <span>{emptyLabel}</span>
      </div>
    );
  }

  const activeFrameRef = frameRef;
  const roiRect = roiToOverlayRect(roi);
  const handles = roiHandlePoints(roi);
  const rotationHandle = roiRotationHandlePoint(roi);
  const pointA =
    detection?.valid === true && detection.point_a ? pointToOverlayCircle(detection.point_a) : null;
  const pointB =
    detection?.valid === true && detection.point_b ? pointToOverlayCircle(detection.point_b) : null;
  const selectedIntervalSegments =
    showDiagnosticsOverlay && detection?.valid === true
      ? diagnosticIntervalsToSegments(detection.diagnostics.selected_valid_intervals, roi)
      : [];
  const rejectedIntervalSegments =
    showDiagnosticsOverlay && detection !== null
      ? [
          ...diagnosticIntervalsToSegments(detection.diagnostics.rejected_intervals, roi),
          ...diagnosticIntervalsToSegments(detection.diagnostics.rejected_remote_intervals, roi),
        ]
      : [];
  const sourceIntervalSegments =
    showDiagnosticsOverlay && detection?.valid === true
      ? [
          ...diagnosticIntervalToSegments(
            detection.diagnostics.point_a_source_interval ??
              detection.diagnostics.formal_point_a_source_interval,
            roi,
          ),
          ...diagnosticIntervalToSegments(
            detection.diagnostics.point_b_source_interval ??
              detection.diagnostics.formal_point_b_source_interval,
            roi,
          ),
        ]
      : [];
  const rejectedA =
    showDiagnosticsOverlay && detection !== null && !detection.valid
      ? diagnosticPointToCircle(detection.diagnostics.rejected_candidate_point_a)
      : null;
  const rejectedB =
    showDiagnosticsOverlay && detection !== null && !detection.valid
      ? diagnosticPointToCircle(detection.diagnostics.rejected_candidate_point_b)
      : null;
  const canEdit = interactive && onRoiChange !== undefined;
  const isInvalidDetection = detection !== null && !detection.valid;
  const measurementLineY = detection?.diagnostics.measurement_line_y;
  const debugMeasurementLine =
    showDiagnosticsOverlay && typeof measurementLineY === "number"
      ? measurementLineSegment(roi, measurementLineY)
      : null;
  const candidateLines =
    showDiagnosticsOverlay && detection !== null
      ? diagnosticCandidateLinesToSegments(detection.diagnostics.top_candidate_lines, roi)
      : [];

  function pointerToAcquisition(event: PointerEvent<SVGSVGElement>): Point2D {
    return clientPointToAcquisition(
      event,
      event.currentTarget.getBoundingClientRect(),
      { width: activeFrameRef.width, height: activeFrameRef.height },
    );
  }

  function handleProbePointerDown(event: PointerEvent<SVGSVGElement>) {
    if (!probeMode || onProbePoint === undefined) {
      return;
    }
    event.stopPropagation();
    onProbePoint(pointerToAcquisition(event));
  }

  function handlePointerDown(event: PointerEvent<SVGSVGElement>) {
    if (!canEdit) {
      return;
    }
    const point = pointerToAcquisition(event);
    const rect = event.currentTarget.getBoundingClientRect();
    const tolerancePx =
      Math.max(activeFrameRef.width / rect.width, activeFrameRef.height / rect.height) * 12;
    const isRotationHandle = hitTestRoiRotationHandle(roi, point, tolerancePx);
    const handle = hitTestRoiHandle(roi, point, tolerancePx);
    event.currentTarget.setPointerCapture(event.pointerId);
    if (isRotationHandle) {
      setDragState({ mode: "rotate" });
    } else if (handle !== null) {
      setDragState({ mode: "resize", handle });
    } else if (pointInsideRoi(roi, point)) {
      setDragState({ mode: "move", last: point });
    } else {
      setDragState({ mode: "create", start: point });
      onRoiChange(createRoiFromDrag(point, point, activeFrameRef, roi.angle_deg));
    }
  }

  function handlePointerMove(event: PointerEvent<SVGSVGElement>) {
    if (!canEdit || dragState === null) {
      return;
    }
    const point = pointerToAcquisition(event);
    if (dragState.mode === "create") {
      onRoiChange(createRoiFromDrag(dragState.start, point, activeFrameRef, roi.angle_deg));
    } else if (dragState.mode === "move") {
      onRoiChange(
        moveRoiByDelta(
          roi,
          point.x - dragState.last.x,
          point.y - dragState.last.y,
          activeFrameRef,
        ),
      );
      setDragState({ mode: "move", last: point });
    } else if (dragState.mode === "resize") {
      onRoiChange(resizeRoiFromHandle(roi, dragState.handle, point, activeFrameRef));
    } else {
      onRoiChange(rotateRoiFromPointer(roi, point, activeFrameRef));
    }
  }

  function handlePointerUp(event: PointerEvent<SVGSVGElement>) {
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
    setDragState(null);
  }

  return (
    <div
      className={[
        "frame-view",
        rawOnly ? "raw-only" : "",
        probeMode ? "probe-mode" : "",
      ]
        .filter(Boolean)
        .join(" ")}
      style={{ aspectRatio: `${activeFrameRef.width} / ${activeFrameRef.height}` }}
    >
      <img
        alt="Frozen acquisition frame"
        className="frame-image"
        onError={() => onPreviewError?.(previewUrl)}
        onLoad={() => onPreviewLoad?.(previewUrl)}
        src={previewUrl}
      />
      {!rawOnly ? (
        <svg
          aria-label="Acquisition overlay"
          className={canEdit ? "frame-overlay editable" : "frame-overlay"}
          onPointerCancel={handlePointerUp}
          onPointerDown={handlePointerDown}
          onPointerMove={handlePointerMove}
          onPointerUp={handlePointerUp}
          ref={svgRef}
          role="img"
          viewBox={`0 0 ${activeFrameRef.width} ${activeFrameRef.height}`}
        >
        <rect
          className={isInvalidDetection ? "roi-overlay invalid" : "roi-overlay"}
          {...roiRect}
          vectorEffect="non-scaling-stroke"
        />
        {isInvalidDetection ? (
          <g className="detection-invalid-banner">
            <rect height="34" rx="4" width="360" x="12" y="12" />
            <text x="26" y="34">
              {detection.status}
            </text>
          </g>
        ) : null}
        {canEdit
          ? [
              <line
                className="roi-rotate-arm"
                key="rotate-arm"
                vectorEffect="non-scaling-stroke"
                x1={handles.n.x}
                x2={rotationHandle.x}
                y1={handles.n.y}
                y2={rotationHandle.y}
              />,
              <circle
                className="roi-rotate-handle"
                cx={rotationHandle.x}
                cy={rotationHandle.y}
                key="rotate-handle"
                r="6"
                vectorEffect="non-scaling-stroke"
              />,
              ...Object.entries(handles).map(([handle, point]) => (
                <circle
                  className="roi-handle"
                  cx={point.x}
                  cy={point.y}
                  key={handle}
                  r="5"
                  vectorEffect="non-scaling-stroke"
                />
              )),
            ]
          : null}
        {rejectedIntervalSegments.map((segment, index) => (
          <line
            className="rejected-interval-segment"
            key={`rej-${segment.x1}-${segment.y1}-${index}`}
            vectorEffect="non-scaling-stroke"
            x1={segment.x1}
            x2={segment.x2}
            y1={segment.y1}
            y2={segment.y2}
          />
        ))}
        {selectedIntervalSegments.map((segment, index) => (
          <line
            className="selected-interval-segment selected-bundle-cluster-segment"
            key={`${segment.x1}-${segment.y1}-${index}`}
            vectorEffect="non-scaling-stroke"
            x1={segment.x1}
            x2={segment.x2}
            y1={segment.y1}
            y2={segment.y2}
          />
        ))}
        {sourceIntervalSegments.map((segment, index) => (
          <line
            className="source-interval-segment"
            key={`src-${segment.x1}-${segment.y1}-${index}`}
            vectorEffect="non-scaling-stroke"
            x1={segment.x1}
            x2={segment.x2}
            y1={segment.y1}
            y2={segment.y2}
          />
        ))}
        {debugMeasurementLine ? (
          <line
            className="debug-measurement-line"
            vectorEffect="non-scaling-stroke"
            x1={debugMeasurementLine.x1}
            x2={debugMeasurementLine.x2}
            y1={debugMeasurementLine.y1}
            y2={debugMeasurementLine.y2}
          />
        ) : null}
        {candidateLines.map((candidate, index) => (
          <line
            className={
              candidate.selected
                ? "candidate-line selected-candidate-line"
                : "candidate-line secondary-candidate-line"
            }
            key={`candidate-${candidate.y1}-${index}`}
            vectorEffect="non-scaling-stroke"
            x1={candidate.x1}
            x2={candidate.x2}
            y1={candidate.y1}
            y2={candidate.y2}
          />
        ))}
        {pointA && pointB ? (
          <line
            className="measurement-line"
            vectorEffect="non-scaling-stroke"
            x1={pointA.cx}
            x2={pointB.cx}
            y1={pointA.cy}
            y2={pointB.cy}
          />
        ) : null}
        {pointA ? <circle className="point point-a" r="4" {...pointA} /> : null}
        {pointB ? <circle className="point point-b" r="4" {...pointB} /> : null}
        {pointA === null && pointB === null && rejectedA && rejectedB ? (
          <line
            className="rejected-debug-line"
            vectorEffect="non-scaling-stroke"
            x1={rejectedA.cx}
            x2={rejectedB.cx}
            y1={rejectedA.cy}
            y2={rejectedB.cy}
          />
        ) : null}
        {pointA === null && rejectedA ? (
          <circle className="rejected-debug-point" r="4" {...rejectedA} />
        ) : null}
        {pointB === null && rejectedB ? (
          <circle className="rejected-debug-point" r="4" {...rejectedB} />
        ) : null}
        {pointA === null && (rejectedA || rejectedB) ? (
          <text
            className="rejected-debug-label"
            x={(rejectedA ?? rejectedB)?.cx ?? 12}
            y={Math.max(16, ((rejectedA ?? rejectedB)?.cy ?? 28) - 10)}
          >
            REJECTED DEBUG
          </text>
        ) : null}
        </svg>
      ) : null}
      {probeMode ? (
        <svg
          aria-label="Probe point layer"
          className="probe-point-layer"
          onPointerDown={handleProbePointerDown}
          role="img"
          viewBox={`0 0 ${activeFrameRef.width} ${activeFrameRef.height}`}
        >
          <rect
            className="probe-point-hit-area"
            height={activeFrameRef.height}
            width={activeFrameRef.width}
            x="0"
            y="0"
          />
        </svg>
      ) : null}
    </div>
  );
}

function diagnosticPointToCircle(value: unknown): { cx: number; cy: number } | null {
  if (typeof value !== "object" || value === null || !("x" in value) || !("y" in value)) {
    return null;
  }
  const point = value as Record<string, unknown>;
  if (typeof point.x !== "number" || typeof point.y !== "number") {
    return null;
  }
  return pointToOverlayCircle({
    x: point.x,
    y: point.y,
    coordinate_space: "acquisition",
  });
}

function diagnosticIntervalsToSegments(
  value: unknown,
  roi: RotatedRoi,
): Array<{ x1: number; y1: number; x2: number; y2: number }> {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.flatMap((item) => {
    if (
      typeof item !== "object" ||
      item === null ||
      !("start_local_x" in item) ||
      !("end_local_x" in item) ||
      !("line_y" in item)
    ) {
      return [];
    }
    const interval = item as Record<string, unknown>;
    if (
      typeof interval.start_local_x !== "number" ||
      typeof interval.end_local_x !== "number" ||
      typeof interval.line_y !== "number"
    ) {
      return [];
    }
    const start = localPointToAcquisition(roi, interval.start_local_x, interval.line_y);
    const end = localPointToAcquisition(roi, interval.end_local_x, interval.line_y);
    return [{ x1: start.x, y1: start.y, x2: end.x, y2: end.y }];
  });
}

function diagnosticIntervalToSegments(
  value: unknown,
  roi: RotatedRoi,
): Array<{ x1: number; y1: number; x2: number; y2: number }> {
  if (typeof value !== "object" || value === null) {
    return [];
  }
  return diagnosticIntervalsToSegments([value], roi);
}

function measurementLineSegment(
  roi: RotatedRoi,
  lineY: number,
): { x1: number; y1: number; x2: number; y2: number } {
  const start = localPointToAcquisition(roi, -roi.width / 2, lineY);
  const end = localPointToAcquisition(roi, roi.width / 2, lineY);
  return { x1: start.x, y1: start.y, x2: end.x, y2: end.y };
}

function diagnosticCandidateLinesToSegments(
  value: unknown,
  roi: RotatedRoi,
): Array<{ x1: number; y1: number; x2: number; y2: number; selected: boolean }> {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.slice(0, 2).flatMap((item) => {
    if (typeof item !== "object" || item === null || !("measurement_line_y" in item)) {
      return [];
    }
    const candidate = item as Record<string, unknown>;
    if (typeof candidate.measurement_line_y !== "number") {
      return [];
    }
    return [
      {
        ...measurementLineSegment(roi, candidate.measurement_line_y),
        selected: candidate.selected === true,
      },
    ];
  });
}

function localPointToAcquisition(
  roi: RotatedRoi,
  localX: number,
  localY: number,
): { x: number; y: number } {
  const angleRad = (roi.angle_deg * Math.PI) / 180;
  const unitX = Math.cos(angleRad);
  const unitY = Math.sin(angleRad);
  const perpX = -unitY;
  const perpY = unitX;
  return {
    x: roi.center_x + localX * unitX + localY * perpX,
    y: roi.center_y + localX * unitY + localY * perpY,
  };
}
