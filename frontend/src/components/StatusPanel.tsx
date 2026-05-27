import type { CameraStatus, SetupDetectResponse } from "../api/types";

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
        <dd>{detection ? detection.quality.toFixed(2) : "-"}</dd>
      </div>
      <div>
        <dt>Distance</dt>
        <dd>{detection?.distance_px !== null && detection ? detection.distance_px.toFixed(2) : "-"}</dd>
      </div>
      <div>
        <dt>Detector</dt>
        <dd>{detection?.detector ?? "-"}</dd>
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
