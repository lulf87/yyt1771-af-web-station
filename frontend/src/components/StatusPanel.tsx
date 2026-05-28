import type { CameraStatus, SetupDetectResponse } from "../api/types";
import { detectionReason, formatNullableNumber, formatPoint } from "./statusDisplay";

interface StatusPanelProps {
  cameraStatus: CameraStatus | null;
  detection: SetupDetectResponse | null;
  error: string | null;
}

export function StatusPanel({ cameraStatus, detection, error }: StatusPanelProps) {
  return (
    <dl className="metric-list">
      <div>
        <dt>Source</dt>
        <dd>{cameraStatus?.opened ? cameraStatus.source_type : "closed"}</dd>
      </div>
      <div>
        <dt>Status</dt>
        <dd>{detection?.status ?? "waiting"}</dd>
      </div>
      <div>
        <dt>Quality</dt>
        <dd>{detection ? detection.quality.toFixed(2) : "N/A"}</dd>
      </div>
      <div>
        <dt>Distance px</dt>
        <dd>{detection ? formatNullableNumber(detection.distance_px) : "N/A"}</dd>
      </div>
      <div>
        <dt>A x,y</dt>
        <dd>{detection ? formatPoint(detection.point_a) : "N/A"}</dd>
      </div>
      <div>
        <dt>B x,y</dt>
        <dd>{detection ? formatPoint(detection.point_b) : "N/A"}</dd>
      </div>
      <div>
        <dt>Detector</dt>
        <dd>{detection?.detector ?? "N/A"}</dd>
      </div>
      <div>
        <dt>Coordinates</dt>
        <dd>{detection?.point_a?.coordinate_space ?? detection?.point_b?.coordinate_space ?? "acquisition"}</dd>
      </div>
      <div>
        <dt>Reason</dt>
        <dd>{detectionReason(detection)}</dd>
      </div>
      {error ? (
        <div className="metric-error">
          <dt>Error</dt>
          <dd>{error}</dd>
        </div>
      ) : null}
    </dl>
  );
}
