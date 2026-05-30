import { useMemo, useState } from "react";

import {
  confirmSetup,
  detectSetupFrame,
  freezeSetupFrame,
  getCameraStatus,
  openCamera,
  wireAutoTune,
} from "../api/client";
import type {
  CameraStatus,
  DetectorParams,
  FrameRef,
  MeasurementDefinition,
  OfflineDataset,
  RotatedRoi,
  SegmentationParams,
  SetupDetectResponse,
  TargetFamily,
  WireAutoTuneResponse,
} from "../api/types";
import { FrameCanvas } from "../components/FrameCanvas";
import { OfflineDatasetSelector } from "../components/OfflineDatasetSelector";
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
    angle_deg: 0,
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
  datasets: OfflineDataset[];
  datasetId: string;
  onDatasetChange: (datasetId: string) => void;
  onMeasurementDefinitionConfirmed: (measurementDefinition: MeasurementDefinition) => void;
}

export function SetupPage({
  datasets,
  datasetId,
  onDatasetChange,
  onMeasurementDefinitionConfirmed,
}: SetupPageProps) {
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
  const [autoTuneResult, setAutoTuneResult] = useState<WireAutoTuneResponse | null>(null);
  const [autoTuned, setAutoTuned] = useState(false);
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
      await openCamera(profile, profile === "dev_offline" ? datasetId || null : null);
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

  async function handleWireAutoTune() {
    if (frameRef === null) {
      setError("Freeze a frame first.");
      return;
    }

    await runAction("auto-tune", async () => {
      const result = await wireAutoTune({
        frame_ref: frameRef,
        roi,
        recipe_name: recipeName,
        target_family: "wire_strip",
        segmentation,
      });
      setAutoTuneResult(result);
      if (result.recommended_segmentation !== null) {
        setSegmentation(result.recommended_segmentation);
        setAutoTuned(true);
      }
      setDetection(null);
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
        auto_tuned: autoTuned,
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
    setAutoTuneResult(null);
    setAutoTuned(false);
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
            <OfflineDatasetSelector
              datasets={datasets}
              disabled={isBusy}
              onChange={onDatasetChange}
              value={datasetId}
            />
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
                setAutoTuned(false);
              }}
            />
          </section>

          {targetFamily === "wire_strip" ? (
            <section className="panel-section">
              <h2>Wire Auto Tune</h2>
              <p className="panel-note">
                Setup-only: sweeps candidate thresholds and recommends the threshold on the widest
                stable platform. The run phase always uses the confirmed recipe.
              </p>
              <div className="button-row compact">
                <button
                  disabled={frameRef === null || isBusy}
                  onClick={handleWireAutoTune}
                  type="button"
                >
                  Run wire auto tune
                </button>
              </div>
              {autoTuneResult ? <WireAutoTunePanel result={autoTuneResult} /> : null}
            </section>
          ) : null}

          <section className="panel-section">
            <h2>Recipe summary</h2>
            <dl className="metric-list compact-list">
              <RecipeSummaryRows
                autoTuned={autoTuned}
                detector={detector}
                segmentation={segmentation}
                targetFamily={targetFamily}
              />
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

function WireAutoTunePanel({ result }: { result: WireAutoTuneResponse }) {
  const platformText =
    result.stable_platform_min !== null && result.stable_platform_max !== null
      ? `${result.stable_platform_min}–${result.stable_platform_max}`
      : "N/A";
  return (
    <div className="auto-tune-result">
      <dl className="metric-list compact-list">
        <div>
          <dt>Recommended threshold</dt>
          <dd>{result.recommended_threshold_value ?? "N/A"}</dd>
        </div>
        <div>
          <dt>Selected reason</dt>
          <dd>{result.selected_reason}</dd>
        </div>
        <div>
          <dt>Stable platform</dt>
          <dd>{platformText}</dd>
        </div>
        <div>
          <dt>Auto tuned</dt>
          <dd>{String(result.auto_tuned)}</dd>
        </div>
      </dl>
      <table className="auto-tune-table">
        <thead>
          <tr>
            <th>thr</th>
            <th>valid</th>
            <th>span</th>
            <th>intervals</th>
            <th>rejected</th>
            <th>broad blob</th>
            <th>wire-like</th>
            <th>score</th>
            <th>platform</th>
          </tr>
        </thead>
        <tbody>
          {result.candidates.map((candidate) => (
            <tr
              className={candidate.on_stable_platform ? "auto-tune-platform-row" : undefined}
              key={candidate.threshold_value}
            >
              <td>{candidate.threshold_value}</td>
              <td>{candidate.valid ? "yes" : "no"}</td>
              <td>{formatNumber(candidate.formal_ab_span_px)}</td>
              <td>{candidate.valid_interval_count ?? "N/A"}</td>
              <td>{candidate.rejected_interval_count}</td>
              <td>{candidate.broad_blob_rejection_count ?? "N/A"}</td>
              <td>{formatNumber(candidate.wire_likeness_score)}</td>
              <td>{formatNumber(candidate.score)}</td>
              <td>{candidate.on_stable_platform ? "✓" : ""}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function formatNumber(value: number | null): string {
  if (value === null || Number.isNaN(value)) {
    return "N/A";
  }
  return value.toFixed(2);
}

function RecipeSummaryRows({
  autoTuned,
  detector,
  segmentation,
  targetFamily,
}: {
  autoTuned: boolean;
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
    ["Auto tuned", autoTuned],
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
