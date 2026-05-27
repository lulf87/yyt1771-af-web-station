import type { FrameRef, RotatedRoi, SetupDetectResponse } from "../api/types";
import { pointToOverlayCircle, roiToOverlayRect } from "../geometry/transforms";

interface FrameCanvasProps {
  frameRef: FrameRef | null;
  previewUrl: string | null;
  roi: RotatedRoi;
  detection: SetupDetectResponse | null;
}

export function FrameCanvas({ frameRef, previewUrl, roi, detection }: FrameCanvasProps) {
  if (frameRef === null || previewUrl === null) {
    return (
      <div className="frame-empty" role="img" aria-label="No frozen frame">
        <span>No frozen frame</span>
      </div>
    );
  }

  const roiRect = roiToOverlayRect(roi);
  const pointA = detection?.point_a ? pointToOverlayCircle(detection.point_a) : null;
  const pointB = detection?.point_b ? pointToOverlayCircle(detection.point_b) : null;

  return (
    <div className="frame-view" style={{ aspectRatio: `${frameRef.width} / ${frameRef.height}` }}>
      <img alt="Frozen acquisition frame" className="frame-image" src={previewUrl} />
      <svg
        aria-label="Acquisition overlay"
        className="frame-overlay"
        role="img"
        viewBox={`0 0 ${frameRef.width} ${frameRef.height}`}
      >
        <rect className="roi-overlay" {...roiRect} vectorEffect="non-scaling-stroke" />
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
