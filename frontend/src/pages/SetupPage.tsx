import { useMemo, useState } from "react";

import {
  confirmSetup,
  detectSetupFrame,
  freezeSetupFrame,
  getCameraStatus,
  openCamera,
} from "../api/client";
import type {
  CameraStatus,
  FrameRef,
  MeasurementDefinition,
  RotatedRoi,
  SetupDetectResponse,
  TargetFamily,
} from "../api/types";
import { FrameCanvas } from "../components/FrameCanvas";
import { RoiEditor } from "../components/RoiEditor";
import { StatusPanel } from "../components/StatusPanel";
import { TargetFamilySelector } from "../components/TargetFamilySelector";

const defaultRois: Record<TargetFamily, RotatedRoi> = {
  balloon_envelope: {
    center_x: 110,
    center_y: 110,
    width: 130,
    height: 80,
    angle_deg: 0,
    coordinate_space: "acquisition",
  },
  wire_strip: {
    center_x: 235,
    center_y: 110,
    width: 55,
    height: 150,
    angle_deg: 90,
    coordinate_space: "acquisition",
  },
};

interface SetupPageProps {
  onMeasurementDefinitionConfirmed: (measurementDefinition: MeasurementDefinition) => void;
}

export function SetupPage({ onMeasurementDefinitionConfirmed }: SetupPageProps) {
  const [cameraStatus, setCameraStatus] = useState<CameraStatus | null>(null);
  const [frameRef, setFrameRef] = useState<FrameRef | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [targetFamily, setTargetFamily] = useState<TargetFamily>("balloon_envelope");
  const [roi, setRoi] = useState<RotatedRoi>(defaultRois.balloon_envelope);
  const [detection, setDetection] = useState<SetupDetectResponse | null>(null);
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const recipeName = useMemo(
    () =>
      targetFamily === "balloon_envelope" ? "balloon_envelope_default" : "wire_strip_default",
    [targetFamily],
  );

  async function refreshStatus() {
    setCameraStatus(await getCameraStatus());
  }

  async function openSource(profile: "dev_mock" | "dev_offline") {
    await runAction(`open-${profile}`, async () => {
      await openCamera(profile);
      await refreshStatus();
      setFrameRef(null);
      setPreviewUrl(null);
      setDetection(null);
    });
  }

  async function handleOpenMock() {
    await openSource("dev_mock");
  }

  async function handleOpenOffline() {
    await openSource("dev_offline");
  }

  async function handleFreeze() {
    await runAction("freeze", async () => {
      const frozen = await freezeSetupFrame();
      setFrameRef(frozen.frame_ref);
      setPreviewUrl(frozen.preview_url);
      setDetection(null);
      await refreshStatus();
    });
  }

  async function handleDetect() {
    if (frameRef === null) {
      setError("Freeze a frame first.");
      return;
    }

    await runAction("detect", async () => {
      const result = await detectSetupFrame({
        frame_ref: frameRef,
        roi,
        target_family: targetFamily,
        recipe_name: recipeName,
      });
      setDetection(result);
    });
  }

  async function handleConfirm() {
    await runAction("confirm", async () => {
      const response = await confirmSetup({
        name: `${targetFamily}-setup`,
        target_family: targetFamily,
        roi,
        recipe_name: recipeName,
      });
      onMeasurementDefinitionConfirmed(response.measurement_definition);
    });
  }

  function handleTargetFamilyChange(nextTargetFamily: TargetFamily) {
    setTargetFamily(nextTargetFamily);
    setRoi(defaultRois[nextTargetFamily]);
    setDetection(null);
  }

  async function runAction(action: string, task: () => Promise<void>) {
    setBusyAction(action);
    setError(null);
    try {
      await task();
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Request failed.");
    } finally {
      setBusyAction(null);
    }
  }

  const hasOpenSource = cameraStatus?.opened === true;
  const isBusy = busyAction !== null;

  return (
    <main className="app-shell">
      <header className="top-bar">
        <div>
          <h1>YYT1771 AF Web Station</h1>
          <p>Setup</p>
        </div>
        <div className="source-pill">
          {hasOpenSource ? `${cameraStatus.source_type} source` : "source closed"}
        </div>
      </header>

      <section className="setup-grid" aria-label="Setup workspace">
        <section className="frame-stage" aria-label="Frame preview">
          <FrameCanvas
            detection={detection}
            frameRef={frameRef}
            interactive
            onRoiChange={(nextRoi) => {
              setRoi(nextRoi);
              setDetection(null);
            }}
            previewUrl={previewUrl}
            roi={roi}
          />
        </section>

        <aside className="setup-panel" aria-label="Setup controls">
          <section className="panel-section">
            <h2>Source</h2>
            <p className="panel-note">Static mock is only a smoke test; offline source uses local .npy frames.</p>
            <div className="button-row compact">
              <button disabled={isBusy} onClick={handleOpenMock} type="button">
                Open mock source
              </button>
              <button disabled={isBusy} onClick={handleOpenOffline} type="button">
                Open offline source
              </button>
              <button disabled={!hasOpenSource || isBusy} onClick={handleFreeze} type="button">
                Freeze latest frame
              </button>
            </div>
          </section>

          <section className="panel-section">
            <h2>Target</h2>
            <TargetFamilySelector value={targetFamily} onChange={handleTargetFamilyChange} />
          </section>

          <section className="panel-section">
            <h2>ROI</h2>
            <RoiEditor roi={roi} onChange={setRoi} />
          </section>

          <section className="panel-section">
            <h2>Result</h2>
            <StatusPanel cameraStatus={cameraStatus} detection={detection} error={error} />
          </section>

          <div className="button-row">
            <button
              disabled={frameRef === null || isBusy}
              onClick={handleConfirm}
              type="button"
            >
              Confirm setup
            </button>
            <button
              className="primary"
              disabled={frameRef === null || isBusy}
              onClick={handleDetect}
              type="button"
            >
              Run detection
            </button>
          </div>
        </aside>
      </section>
    </main>
  );
}
