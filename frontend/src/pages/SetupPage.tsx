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
  DetectorParams,
  FrameRef,
  MeasurementDefinition,
  RotatedRoi,
  SegmentationParams,
  SetupDetectResponse,
  TargetFamily,
} from "../api/types";
import { FrameCanvas } from "../components/FrameCanvas";
import { RoiEditor } from "../components/RoiEditor";
import { SegmentationControls } from "../components/SegmentationControls";
import { StatusPanel } from "../components/StatusPanel";
import { TargetFamilySelector } from "../components/TargetFamilySelector";
import {
  debugOverlayUrlWithLayers,
  type DebugOverlayLayers,
} from "./setupDebugOverlay";
import { balloonRecipeForEnvelopeMode, recipeDefaultsForTarget } from "../setup/recipeDefaults";

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

const defaultDebugOverlayLayers: DebugOverlayLayers = {
  showRawForeground: true,
  showMorphologyForeground: true,
  showFilledEnvelope: true,
  showSelectedContour: true,
  showRejectedCandidates: true,
};

const debugOverlayLayerFields: Array<{
  key: keyof DebugOverlayLayers;
  label: string;
}> = [
  { key: "showRawForeground", label: "show raw foreground" },
  { key: "showMorphologyForeground", label: "show bridged/morphology foreground" },
  { key: "showFilledEnvelope", label: "show filled envelope debug layer" },
  { key: "showSelectedContour", label: "show selected contour" },
  { key: "showRejectedCandidates", label: "show rejected candidates" },
];

interface SetupPageProps {
  onMeasurementDefinitionConfirmed: (measurementDefinition: MeasurementDefinition) => void;
}

export function SetupPage({ onMeasurementDefinitionConfirmed }: SetupPageProps) {
  const [cameraStatus, setCameraStatus] = useState<CameraStatus | null>(null);
  const [frameRef, setFrameRef] = useState<FrameRef | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [targetFamily, setTargetFamily] = useState<TargetFamily>("balloon_envelope");
  const [roi, setRoi] = useState<RotatedRoi>(defaultRois.balloon_envelope);
  const [segmentation, setSegmentation] = useState<SegmentationParams>(
    recipeDefaultsForTarget("balloon_envelope").segmentation,
  );
  const [detector, setDetector] = useState<DetectorParams>(
    recipeDefaultsForTarget("balloon_envelope").detector,
  );
  const [debugOverlayLayers, setDebugOverlayLayers] = useState<DebugOverlayLayers>(
    defaultDebugOverlayLayers,
  );
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

  async function openSource(profile: "dev_mock" | "dev_offline" | "dev_lab") {
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

  async function handleOpenLab() {
    await openSource("dev_lab");
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
        segmentation,
        detector,
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
        segmentation,
        detector,
      });
      onMeasurementDefinitionConfirmed(response.measurement_definition);
    });
  }

  function handleTargetFamilyChange(nextTargetFamily: TargetFamily) {
    setTargetFamily(nextTargetFamily);
    const defaults = recipeDefaultsForTarget(nextTargetFamily);
    setRoi(defaultRois[nextTargetFamily]);
    setSegmentation(defaults.segmentation);
    setDetector(defaults.detector);
    setDetection(null);
  }

  function handleDetectorChange(nextDetector: DetectorParams) {
    if (
      detector.detector_kind === "balloon_envelope_detector" &&
      nextDetector.detector_kind === "balloon_envelope_detector" &&
      detector.envelope_mode !== nextDetector.envelope_mode
    ) {
      const recommended = balloonRecipeForEnvelopeMode(nextDetector.envelope_mode);
      setSegmentation(recommended.segmentation);
      setDetector(recommended.detector);
    } else {
      setDetector(nextDetector);
    }
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
  const debugOverlayUrl = debugOverlayUrlWithLayers(
    detection?.debug_overlay_url,
    debugOverlayLayers,
  );

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
          {debugOverlayUrl ? (
            <section className="debug-overlay-panel" aria-label="Detection debug overlay">
              <h2>Debug mask / component / contour</h2>
              <div className="debug-layer-controls">
                {debugOverlayLayerFields.map((field) => (
                  <label className="inline-check" key={field.key}>
                    <input
                      checked={debugOverlayLayers[field.key]}
                      onChange={(event) =>
                        setDebugOverlayLayers({
                          ...debugOverlayLayers,
                          [field.key]: event.currentTarget.checked,
                        })
                      }
                      type="checkbox"
                    />
                    <span>{field.label}</span>
                  </label>
                ))}
              </div>
              <img alt="Detection debug overlay" src={debugOverlayUrl} />
            </section>
          ) : null}
        </section>

        <aside className="setup-panel" aria-label="Setup controls">
          <section className="panel-section">
            <h2>Source</h2>
            <p className="panel-note">
              Static mock is only a smoke test; offline source uses local .npy frames; lab source
              uses the optional Hik MVS adapter.
            </p>
            <div className="button-row compact">
              <button disabled={isBusy} onClick={handleOpenMock} type="button">
                Open mock source
              </button>
              <button disabled={isBusy} onClick={handleOpenOffline} type="button">
                Open offline source
              </button>
              <button disabled={isBusy} onClick={handleOpenLab} type="button">
                Open lab source
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
            <h2>Segmentation Debug</h2>
            <p className="panel-note">
              These controls only affect current setup detection and confirmed local recipe data.
            </p>
            <SegmentationControls
              detector={detector}
              onDetectorChange={handleDetectorChange}
              value={segmentation}
              onChange={(nextSegmentation) => {
                setSegmentation(nextSegmentation);
                setDetection(null);
              }}
            />
          </section>

          <section className="panel-section">
            <h2>Recipe summary</h2>
            <dl className="metric-list compact-list">
              <RecipeSummaryRows detector={detector} segmentation={segmentation} targetFamily={targetFamily} />
            </dl>
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

function RecipeSummaryRows({
  detector,
  segmentation,
  targetFamily,
}: {
  detector: DetectorParams;
  segmentation: SegmentationParams;
  targetFamily: TargetFamily;
}) {
  const envelopeMode =
    detector.detector_kind === "balloon_envelope_detector" ? detector.envelope_mode : "N/A";
  const contactSource =
    detector.detector_kind === "balloon_envelope_detector" ? detector.contact_source : "N/A";
  const measurementMode =
    detector.detector_kind === "wire_strip_detector" ? detector.measurement_mode : "N/A";
  const rows: Array<[string, string | number | boolean | null | undefined]> = [
    ["Target", targetFamily],
    ["Measurement model", detector.measurement_model],
    ["Measurement mode", measurementMode],
    ["Envelope mode", envelopeMode],
    ["Contact source", contactSource],
    ["Polarity", segmentation.polarity],
    ["Threshold mode", segmentation.threshold_mode],
    ["Threshold", segmentation.threshold_value],
    ["Fill holes", segmentation.fill_internal_holes ?? false],
    ["Close kernel", segmentation.close_kernel],
    ["Open kernel", segmentation.open_kernel],
    ["Min area", segmentation.min_component_area_px],
  ];
  return (
    <>
      {rows.map(([label, value]) => (
        <div key={label}>
          <dt>{label}</dt>
          <dd>{value === null || value === undefined ? "N/A" : String(value)}</dd>
        </div>
      ))}
    </>
  );
}
