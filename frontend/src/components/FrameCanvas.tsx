import { useRef, useState } from "react";
import type { PointerEvent } from "react";

import type { FrameRef, Point2D, RotatedRoi, SetupDetectResponse } from "../api/types";
import {
  clientPointToAcquisition,
  createRoiFromDrag,
  hitTestRoiHandle,
  moveRoiByDelta,
  pointInsideRoi,
  pointToOverlayCircle,
  resizeRoiFromHandle,
  roiHandlePoints,
  roiToOverlayRect,
  type RoiHandle,
} from "../geometry/transforms";

interface FrameCanvasProps {
  frameRef: FrameRef | null;
  previewUrl: string | null;
  roi: RotatedRoi;
  detection: SetupDetectResponse | null;
  interactive?: boolean;
  onRoiChange?: (roi: RotatedRoi) => void;
  emptyLabel?: string;
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
    };

export function FrameCanvas({
  frameRef,
  previewUrl,
  roi,
  detection,
  interactive = false,
  onRoiChange,
  emptyLabel = "No frozen frame",
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
  const pointA = detection?.point_a ? pointToOverlayCircle(detection.point_a) : null;
  const pointB = detection?.point_b ? pointToOverlayCircle(detection.point_b) : null;
  const canEdit = interactive && onRoiChange !== undefined;
  const isInvalidDetection = detection !== null && !detection.valid;

  function pointerToAcquisition(event: PointerEvent<SVGSVGElement>): Point2D {
    if (svgRef.current === null) {
      return { x: 0, y: 0, coordinate_space: "acquisition" };
    }
    return clientPointToAcquisition(
      event,
      svgRef.current.getBoundingClientRect(),
      { width: activeFrameRef.width, height: activeFrameRef.height },
    );
  }

  function handlePointerDown(event: PointerEvent<SVGSVGElement>) {
    if (!canEdit) {
      return;
    }
    const point = pointerToAcquisition(event);
    const rect = event.currentTarget.getBoundingClientRect();
    const tolerancePx =
      Math.max(activeFrameRef.width / rect.width, activeFrameRef.height / rect.height) * 12;
    const handle = hitTestRoiHandle(roi, point, tolerancePx);
    event.currentTarget.setPointerCapture(event.pointerId);
    if (handle !== null) {
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
    } else {
      onRoiChange(resizeRoiFromHandle(roi, dragState.handle, point, activeFrameRef));
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
      className="frame-view"
      style={{ aspectRatio: `${activeFrameRef.width} / ${activeFrameRef.height}` }}
    >
      <img alt="Frozen acquisition frame" className="frame-image" src={previewUrl} />
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
          ? Object.entries(handles).map(([handle, point]) => (
              <circle
                className="roi-handle"
                cx={point.x}
                cy={point.y}
                key={handle}
                r="5"
                vectorEffect="non-scaling-stroke"
              />
            ))
          : null}
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
      </svg>
    </div>
  );
}
