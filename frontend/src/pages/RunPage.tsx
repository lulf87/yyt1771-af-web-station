import { useEffect, useRef, useState } from "react";

import {
  ApiRequestError,
  closeOfflineRun,
  getRunSamples,
  getRunStatus,
  inspectOfflineRun,
  nextOfflineRun,
  openOfflineRun,
  previousOfflineRun,
  seekOfflineRun,
  startRun,
  stopRun,
} from "../api/client";
import type {
  CameraStatus,
  FrameRef,
  MeasurementDefinition,
  OfflineDataset,
  OfflineRunFrame,
  OfflineRunOpenResponse,
  RunSample,
  RunStatusResponse,
} from "../api/types";
import { FrameCanvas } from "../components/FrameCanvas";
import { OfflineDatasetSelector } from "../components/OfflineDatasetSelector";
import { StatusPanel } from "../components/StatusPanel";
import { TemperaturePanel } from "../components/TemperaturePanel";
import { latestSample, sampleRows } from "../run/sampleDisplay";
import { formatPlaybackTime, runtimeNumber, runtimeString } from "../run/liveOfflineDisplay";

interface RunPageProps {
  datasets: OfflineDataset[];
  datasetId: string;
  onDatasetChange: (datasetId: string) => void;
  measurementDefinition: MeasurementDefinition | null;
}

type RunMode = "batch" | "live_offline";

interface LiveRunErrorInfo {
  message: string;
  errorCode: string | null;
  frameIndex: number | null;
  frameName: string | null;
}

const fallbackRoi = {
  center_x: 1,
  center_y: 1,
  width: 1,
  height: 1,
  angle_deg: 0,
  coordinate_space: "acquisition" as const,
};

export function RunPage({
  datasets,
  datasetId,
  onDatasetChange,
  measurementDefinition,
}: RunPageProps) {
  const [runMode, setRunMode] = useState<RunMode>("live_offline");
  const [runStatus, setRunStatus] = useState<RunStatusResponse | null>(null);
  const [samples, setSamples] = useState<RunSample[]>([]);
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [offlineRun, setOfflineRun] = useState<OfflineRunOpenResponse | null>(null);
  const [liveFrame, setLiveFrame] = useState<OfflineRunFrame | null>(null);
  const [liveApiError, setLiveApiError] = useState<LiveRunErrorInfo | null>(null);
  const [livePreviewError, setLivePreviewError] = useState<LiveRunErrorInfo | null>(null);
  const [lastSuccessfulLiveFrameIndex, setLastSuccessfulLiveFrameIndex] = useState<number | null>(
    null,
  );
  const [failedLiveFrameIndex, setFailedLiveFrameIndex] = useState<number | null>(null);
  const [liveFps, setLiveFps] = useState(10);
  const [liveLoop, setLiveLoop] = useState(true);
  const [isLivePlaying, setIsLivePlaying] = useState(false);
  const [liveFrameIntervalMs, setLiveFrameIntervalMs] = useState<number | null>(null);
  const inFlightLiveRequest = useRef(false);
  const liveTimer = useRef<number | null>(null);
  const liveSessionIdRef = useRef<string | null>(null);
  const liveFpsRef = useRef(liveFps);
  liveFpsRef.current = liveFps;
  const lastFrameArrivalRef = useRef<number | null>(null);
  const liveNextAbortControllerRef = useRef<AbortController | null>(null);
  const advanceLiveNextRef = useRef<
    (args: { fromPlaybackLoop: boolean }) => Promise<OfflineRunFrame | null>
  >(async () => null);

  const frameCount = offlineRun?.frame_count ?? 0;
  const maxLiveIndex = Math.max(0, frameCount - 1);
  const currentLiveIndex = liveFrame?.frame_index ?? offlineRun?.current_frame_index ?? 0;

  const latest = latestSample(samples);
  const latestFrameRef = latest?.detection.frame_ref ?? null;
  const latestPreviewUrl =
    latestFrameRef === null
      ? null
      : `/api/camera/frame/${latestFrameRef.frame_id}/preview.png?max_width=1200`;
  const liveFrameRef = frameRefFromOfflineRunFrame(liveFrame);
  const liveCameraStatus = cameraStatusFromOfflineRunFrame(liveFrame, offlineRun !== null);
  const activeDetection =
    runMode === "live_offline" ? (liveFrame?.detection ?? null) : (latest?.detection ?? null);
  const activeFrameRef = runMode === "live_offline" ? liveFrameRef : latestFrameRef;
  const activePreviewUrl = runMode === "live_offline" ? liveFrame?.preview_url ?? null : latestPreviewUrl;
  const rows = sampleRows(samples).slice(-12).reverse();
  const chartSamples = samples.slice(-24);
  const maxDistance = Math.max(
    1,
    ...chartSamples.map((sample) => sample.detection.distance_px ?? 0),
  );
  const liveRelativeTimeS =
    runMode === "live_offline" ? (liveFrame?.relative_time_s ?? null) : null;
  const liveTotalDurationS =
    runMode === "live_offline" && offlineRun !== null && frameCount > 0
      ? runtimeNumber(liveFrame?.runtime, "total_duration_s") ??
        maxLiveIndex / Math.max(1, liveFps)
      : null;
  const liveTemperatureC =
    runMode === "live_offline"
      ? runtimeNumber(liveFrame?.runtime, "temperature_c")
      : null;
  const liveTemperatureStatus =
    runMode === "live_offline"
      ? runtimeString(liveFrame?.runtime, "temperature_status")
      : null;
  const liveTemperatureSource =
    runMode === "live_offline"
      ? runtimeString(liveFrame?.runtime, "temperature_source")
      : null;
  const activeTemperatureC =
    runMode === "live_offline" ? liveTemperatureC : (latest?.temperature_c ?? null);
  const liveState =
    liveApiError !== null && offlineRun !== null
      ? "api_error"
      : livePreviewError !== null && offlineRun !== null
        ? "preview_error"
        : offlineRun === null
          ? "unopened"
          : liveFrame?.end_of_stream
            ? "end_of_stream"
            : isLivePlaying
              ? "playing"
              : "paused";
  const liveControlError = liveApiError?.message ?? livePreviewError?.message ?? error;
  const liveControlErrorKind =
    liveApiError !== null
      ? "API error"
      : livePreviewError !== null
        ? "Preview error"
        : error !== null
          ? "Error"
          : null;

  useEffect(() => {
    liveSessionIdRef.current = offlineRun?.session_id ?? null;
  }, [offlineRun?.session_id]);

  useEffect(() => {
    return () => {
      liveNextAbortControllerRef.current?.abort();
      const sessionId = liveSessionIdRef.current;
      if (sessionId !== null) {
        void closeOfflineRun(sessionId);
      }
    };
  }, []);

  function markLiveFrameSuccess(frame: OfflineRunFrame) {
    setLiveFrame(frame);
    setLiveApiError(null);
    setLivePreviewError(null);
    setLastSuccessfulLiveFrameIndex(frame.frame_index);
    setFailedLiveFrameIndex(null);
  }

  function liveErrorFromCaught(caughtError: unknown, fallback: string): LiveRunErrorInfo {
    if (caughtError instanceof ApiRequestError) {
      return {
        message:
          caughtError.errorCode !== null
            ? `${caughtError.errorCode}: ${caughtError.message}`
            : caughtError.message,
        errorCode: caughtError.errorCode,
        frameIndex: caughtError.frameIndex,
        frameName: caughtError.frameName,
      };
    }
    return {
      message: caughtError instanceof Error ? caughtError.message : fallback,
      errorCode: null,
      frameIndex: null,
      frameName: null,
    };
  }

  function recordLiveApiError(caughtError: unknown, fallback = "Request failed.") {
    const apiError = liveErrorFromCaught(caughtError, fallback);
    setLiveApiError(apiError);
    setFailedLiveFrameIndex(apiError.frameIndex);
    setIsLivePlaying(false);
    return apiError;
  }

  function handlePreviewError(previewUrl: string) {
    const frameIndex = liveFrame?.preview_url === previewUrl ? liveFrame.frame_index : null;
    const frameName = liveFrame?.preview_url === previewUrl ? liveFrame.frame_name : null;
    setIsLivePlaying(false);
    setLivePreviewError({
      message: `preview_fetch_failed: preview image failed to load for frame ${
        frameIndex === null ? "unknown" : frameIndex
      }.`,
      errorCode: "preview_fetch_failed",
      frameIndex,
      frameName,
    });
    setFailedLiveFrameIndex(frameIndex);
  }

  function handlePreviewLoad(previewUrl: string) {
    if (livePreviewError !== null && liveFrame?.preview_url === previewUrl) {
      setLivePreviewError(null);
    }
  }

  async function handleStart() {
    if (measurementDefinition === null) {
      setError("Confirm setup before starting a run.");
      return;
    }

    await runAction("start", async () => {
      const started = await startRun({
        measurement_definition_id: measurementDefinition.measurement_definition_id,
        sample_hz: 10,
        sample_count: 10,
      });
      const [status, samplePayload] = await Promise.all([
        getRunStatus(started.run_id),
        getRunSamples(started.run_id),
      ]);
      setRunStatus(status);
      setSamples(samplePayload.samples);
    });
  }

  async function handleStop() {
    if (runStatus === null) {
      return;
    }
    await runAction("stop", async () => {
      await stopRun(runStatus.run_id);
      setRunStatus(await getRunStatus(runStatus.run_id));
    });
  }

  async function handleOpenLive() {
    if (measurementDefinition === null) {
      setError("Confirm setup before opening live offline run.");
      return;
    }

    await runAction("open-live", async () => {
      const opened = await openOfflineRun({
        measurement_definition_id: measurementDefinition.measurement_definition_id,
        frames_dir: null,
        dataset_id: datasetId || null,
        fps: liveFps,
        loop: liveLoop,
        dataset_label: null,
        start_frame_index: 0,
        max_preview_width: 960,
      });
      setOfflineRun(opened);
      setIsLivePlaying(false);
      setLiveApiError(null);
      setLivePreviewError(null);
      setLastSuccessfulLiveFrameIndex(null);
      setFailedLiveFrameIndex(null);
      const firstFrame = await seekOfflineRun(opened.session_id, opened.current_frame_index);
      markLiveFrameSuccess(firstFrame);
    });
  }

  async function stopLiveOfflineSession() {
    setIsLivePlaying(false);
    liveNextAbortControllerRef.current?.abort();
    liveNextAbortControllerRef.current = null;
    if (liveTimer.current !== null) {
      window.clearTimeout(liveTimer.current);
      liveTimer.current = null;
    }
    if (offlineRun === null) {
      return;
    }
    try {
      await closeOfflineRun(offlineRun.session_id);
    } catch {
      // Session may already be closed during unmount.
    }
    setOfflineRun(null);
    setLiveFrame(null);
    setLiveApiError(null);
    setLivePreviewError(null);
    setLastSuccessfulLiveFrameIndex(null);
    setFailedLiveFrameIndex(null);
    liveSessionIdRef.current = null;
  }

  async function handleCloseLive() {
    if (offlineRun === null) {
      return;
    }
    await runAction("close-live", async () => {
      await stopLiveOfflineSession();
    });
  }

  async function handleLivePrevious() {
    if (offlineRun === null) {
      return;
    }
    await runAction("live-previous", async () => {
      setIsLivePlaying(false);
      liveNextAbortControllerRef.current?.abort();
      markLiveFrameSuccess(await previousOfflineRun(offlineRun.session_id));
    });
  }

  async function handleLiveNext() {
    if (offlineRun === null) {
      return;
    }
    const nextIndex =
      currentLiveIndex >= maxLiveIndex ? (liveLoop ? 0 : maxLiveIndex) : currentLiveIndex + 1;
    await handleLiveSeek(nextIndex);
  }

  async function handleLiveInspect() {
    if (offlineRun === null) {
      return;
    }
    await runAction("live-inspect", async () => {
      setIsLivePlaying(false);
      liveNextAbortControllerRef.current?.abort();
      markLiveFrameSuccess(await inspectOfflineRun(offlineRun.session_id));
    });
  }

  async function handleLivePlayPause() {
    if (offlineRun === null) {
      return;
    }
    if (!isLivePlaying) {
      setLiveApiError(null);
      setLivePreviewError(null);
      setError(null);
      setLiveFrameIntervalMs(null);
      setIsLivePlaying(true);
      return;
    }
    await runAction("live-pause", async () => {
      setIsLivePlaying(false);
      liveNextAbortControllerRef.current?.abort();
      liveNextAbortControllerRef.current = null;
      markLiveFrameSuccess(await inspectOfflineRun(offlineRun.session_id));
    });
  }

  async function handleLiveSeek(frameIndex: number) {
    if (offlineRun === null) {
      return;
    }
    await runAction("live-seek", async () => {
      setIsLivePlaying(false);
      liveNextAbortControllerRef.current?.abort();
      markLiveFrameSuccess(await seekOfflineRun(offlineRun.session_id, frameIndex));
    });
  }

  async function advanceLiveNext({
    fromPlaybackLoop,
  }: {
    fromPlaybackLoop: boolean;
  }): Promise<OfflineRunFrame | null> {
    if (offlineRun === null || inFlightLiveRequest.current) {
      return null;
    }
    inFlightLiveRequest.current = true;
    if (!fromPlaybackLoop) {
      setBusyAction("live-next");
      setError(null);
    }
    const abortController = new AbortController();
    liveNextAbortControllerRef.current = abortController;
    try {
      const frame = await nextOfflineRun(offlineRun.session_id, abortController.signal);
      markLiveFrameSuccess(frame);
      if (frame.end_of_stream) {
        setIsLivePlaying(false);
      }
      return frame;
    } catch (caughtError) {
      if (caughtError instanceof DOMException && caughtError.name === "AbortError") {
        return null;
      }
      recordLiveApiError(caughtError);
      return null;
    } finally {
      if (liveNextAbortControllerRef.current === abortController) {
        liveNextAbortControllerRef.current = null;
      }
      inFlightLiveRequest.current = false;
      if (!fromPlaybackLoop) {
        setBusyAction(null);
      }
    }
  }

  advanceLiveNextRef.current = advanceLiveNext;

  useEffect(() => {
    if (!isLivePlaying || offlineRun === null) {
      return undefined;
    }

    let cancelled = false;
    let wakeTimer: number | null = null;
    lastFrameArrivalRef.current = null;

    const sleep = (delayMs: number) =>
      new Promise<void>((resolve) => {
        wakeTimer = window.setTimeout(resolve, delayMs);
      });

    void (async () => {
      while (!cancelled) {
        const startedAt = performance.now();
        const frame = await advanceLiveNextRef.current({ fromPlaybackLoop: true });
        if (cancelled || frame?.end_of_stream) {
          break;
        }
        if (frame === null) {
          await sleep(10);
          continue;
        }
        // Measured wall-clock interval between rendered playback frames. This is
        // the real perceived playback rate (1000 / interval ~= fps).
        const arrivedAt = performance.now();
        if (lastFrameArrivalRef.current !== null) {
          setLiveFrameIntervalMs(
            Math.round((arrivedAt - lastFrameArrivalRef.current) * 10) / 10,
          );
        }
        lastFrameArrivalRef.current = arrivedAt;
        const elapsedMs = performance.now() - startedAt;
        const waitMs = Math.max(0, 1000 / Math.max(1, liveFpsRef.current) - elapsedMs);
        if (waitMs > 0) {
          await sleep(waitMs);
        }
      }
    })();

    return () => {
      cancelled = true;
      lastFrameArrivalRef.current = null;
      if (wakeTimer !== null) {
        window.clearTimeout(wakeTimer);
      }
    };
  }, [isLivePlaying, offlineRun?.session_id, liveFps]);

  async function runAction(action: string, task: () => Promise<void>) {
    setBusyAction(action);
    setError(null);
    try {
      await task();
    } catch (caughtError) {
      if (action.startsWith("live-") || action === "open-live" || action === "close-live") {
        const apiError = recordLiveApiError(caughtError);
        setError(apiError.message);
      } else {
        setError(caughtError instanceof Error ? caughtError.message : "Request failed.");
      }
    } finally {
      setBusyAction(null);
    }
  }

  const isBusy = busyAction !== null;

  return (
    <main className="app-shell">
      <header className="top-bar">
        <div>
          <h1>YYT1771 AF Web Station</h1>
          <p>Run</p>
        </div>
        <div className="source-pill">
          {measurementDefinition ? measurementDefinition.measurement_definition_id : "no setup"}
        </div>
      </header>

      <section className="run-grid" aria-label="Run workspace">
        <section className="run-main" aria-label="Run frame and samples">
          <section className="run-summary">
            <div className="summary-tile">
              <span>Distance</span>
              <strong>
                {activeDetection?.distance_px === null || !activeDetection
                  ? "-"
                  : activeDetection.distance_px.toFixed(2)}
              </strong>
            </div>
            <div className="summary-tile">
              <span>Status</span>
              <strong>{activeDetection?.status ?? "waiting"}</strong>
            </div>
            <div className="summary-tile">
              <span>Quality</span>
              <strong>{activeDetection ? activeDetection.quality.toFixed(2) : "-"}</strong>
            </div>
            {runMode === "live_offline" ? (
              <div className="summary-tile">
                <span>Material time</span>
                <strong>
                  {liveRelativeTimeS === null || liveTotalDurationS === null
                    ? "-"
                    : `${formatPlaybackTime(liveRelativeTimeS)} / ${formatPlaybackTime(liveTotalDurationS)}`}
                </strong>
              </div>
            ) : (
              <div className="summary-tile">
                <span>Temperature</span>
                <strong>
                  {activeTemperatureC === null ? "-" : activeTemperatureC.toFixed(1)}
                </strong>
              </div>
            )}
            {runMode === "live_offline" ? (
              <div className="summary-tile">
                <span>Temperature</span>
                <strong>
                  {activeTemperatureC === null
                    ? "-"
                    : `${activeTemperatureC.toFixed(1)}°C${liveTemperatureStatus ? ` (${liveTemperatureStatus})` : ""}${liveTemperatureSource ? ` · ${liveTemperatureSource}` : ""}`}
                </strong>
              </div>
            ) : null}

            <div className="run-chart" aria-label="Recent distance samples">
              {chartSamples.map((sample) => {
                const distance = sample.detection.distance_px;
                const height = distance === null ? 8 : Math.max(8, (distance / maxDistance) * 130);
                return (
                  <div
                    className={distance === null ? "bar invalid" : "bar"}
                    key={sample.sample_index}
                    style={{ height }}
                    title={`${sample.sample_index}: ${sample.detection.status}, ${sample.temperature_status}`}
                  />
                );
              })}
            </div>
          </section>

          <section className="frame-stage compact-frame" aria-label="Latest run frame">
            <FrameCanvas
              detection={activeDetection}
              emptyLabel={
                runMode === "live_offline"
                  ? "Open Live Offline Run to show simulated camera frames"
                  : "Start a run to show the latest frame"
              }
              frameRef={activeFrameRef}
              onPreviewError={runMode === "live_offline" ? handlePreviewError : undefined}
              onPreviewLoad={runMode === "live_offline" ? handlePreviewLoad : undefined}
              previewUrl={activePreviewUrl}
              roi={measurementDefinition?.roi ?? fallbackRoi}
              showDiagnosticsOverlay={runMode === "live_offline" && !isLivePlaying}
            />
          </section>
        </section>

        <aside className="setup-panel" aria-label="Run controls">
          <TemperaturePanel />

          <section className="panel-section">
            <h2>Mode</h2>
            <div className="segmented-control two-up">
              <button
                aria-pressed={runMode === "batch"}
                className={runMode === "batch" ? "segment active" : "segment"}
                onClick={() => {
                  void stopLiveOfflineSession();
                  setRunMode("batch");
                }}
                type="button"
              >
                Batch Run
              </button>
              <button
                aria-pressed={runMode === "live_offline"}
                className={runMode === "live_offline" ? "segment active" : "segment"}
                onClick={() => setRunMode("live_offline")}
                type="button"
              >
                Live Offline Run
              </button>
            </div>
          </section>

          {runMode === "batch" ? (
            <BatchRunControls
              error={error}
              isBusy={isBusy}
              measurementDefinition={measurementDefinition}
              onStart={handleStart}
              onStop={handleStop}
              runStatus={runStatus}
              samplesLength={samples.length}
            />
          ) : (
            <LiveOfflineRunControls
              currentIndex={currentLiveIndex}
              datasetId={datasetId}
              datasets={datasets}
              distance={activeDetection?.distance_px ?? null}
              error={liveControlError}
              errorKind={liveControlErrorKind}
              failedFrameIndex={failedLiveFrameIndex}
              fps={liveFps}
              frameCount={frameCount}
              frameName={liveFrame?.frame_name ?? null}
              isBusy={isBusy}
              isPlaying={isLivePlaying}
              lastSuccessfulFrameIndex={lastSuccessfulLiveFrameIndex}
              loop={liveLoop}
              maxIndex={maxLiveIndex}
              measurementDefinition={measurementDefinition}
              onClose={handleCloseLive}
              onDatasetChange={onDatasetChange}
              onFpsChange={setLiveFps}
              onLoopChange={setLiveLoop}
              onInspect={handleLiveInspect}
              onNext={handleLiveNext}
              onOpen={handleOpenLive}
              onPlayPause={handleLivePlayPause}
              onPrevious={handleLivePrevious}
              onSeek={handleLiveSeek}
              quality={activeDetection?.quality ?? null}
              relativeTimeS={liveRelativeTimeS}
              state={liveState}
              status={activeDetection?.status ?? "waiting"}
              temperatureC={liveTemperatureC}
              temperatureSource={liveTemperatureSource}
              temperatureStatus={liveTemperatureStatus}
              totalDurationS={liveTotalDurationS}
            />
          )}

          {runMode === "live_offline" ? (
            <section className="panel-section">
              <h2>Diagnostics</h2>
              <LiveTimingReadout
                runtime={liveFrame?.runtime}
                frameIntervalMs={isLivePlaying ? liveFrameIntervalMs : null}
              />
              <StatusPanel
                cameraStatus={liveCameraStatus}
                detection={activeDetection}
                error={liveControlError}
                showDebugDiagnostics={!isLivePlaying}
              />
            </section>
          ) : null}
        </aside>
      </section>

      <section className="samples-panel" aria-label="Recent samples">
        <h2>Recent samples</h2>
        <div className="samples-table">
          <div className="samples-header">
            <span>#</span>
            <span>Status</span>
            <span>Distance</span>
            <span>Temperature</span>
            <span>Quality</span>
          </div>
          {rows.map((row) => (
            <div className="sample-row" key={row.index}>
              <span>{row.index}</span>
              <span>{row.status}</span>
              <span>{row.distance}</span>
              <span title={row.temperatureStatus}>{row.temperature}</span>
              <span>{row.quality}</span>
            </div>
          ))}
        </div>
      </section>
    </main>
  );
}

function LiveTimingReadout({
  runtime,
  frameIntervalMs,
}: {
  runtime: Record<string, unknown> | undefined;
  frameIntervalMs: number | null;
}) {
  const detectMs = runtimeNumber(runtime, "detect_ms");
  const loadMs = runtimeNumber(runtime, "frame_load_ms") ?? runtimeNumber(runtime, "load_ms");
  const apiTotalMs = runtimeNumber(runtime, "api_total_ms");
  const previewEncodeMs = runtimeNumber(runtime, "preview_encode_ms");
  const targetFps = runtimeNumber(runtime, "target_fps") ?? runtimeNumber(runtime, "fps");
  const frameBudgetMs =
    runtimeNumber(runtime, "frame_budget_ms") ??
    (targetFps !== null && targetFps > 0 ? Math.round((1000 / targetFps) * 1000) / 1000 : null);
  const segmentationMs = runtimeNumber(runtime, "segmentation_ms");
  const connectedComponentsMs = runtimeNumber(runtime, "connected_components_ms");
  const wireFilteringMs = runtimeNumber(runtime, "wire_filtering_ms");
  const lineScanMs = runtimeNumber(runtime, "line_scan_ms");
  const candidateScoringMs = runtimeNumber(runtime, "candidate_scoring_ms");
  const diagnosticsMs = runtimeNumber(runtime, "diagnostics_ms");
  const detectorTotalMs = runtimeNumber(runtime, "detector_total_ms");
  const debugLevel = runtimeString(runtime, "debug_level");
  const measuredFps =
    frameIntervalMs !== null && frameIntervalMs > 0
      ? Math.round((1000 / frameIntervalMs) * 10) / 10
      : null;
  const rows: Array<[string, string]> = [
    ["Measured fps", measuredFps !== null ? `${measuredFps}` : "N/A"],
    ["Target fps", targetFps !== null ? `${targetFps}` : "N/A"],
    ["Frame interval ms", frameIntervalMs !== null ? `${frameIntervalMs}` : "N/A"],
    ["Frame budget ms", frameBudgetMs !== null ? `${frameBudgetMs}` : "N/A"],
    ["Detect ms", detectMs !== null ? `${detectMs}` : "N/A"],
    ["Segmentation ms", segmentationMs !== null ? `${segmentationMs}` : "N/A"],
    [
      "Connected components ms",
      connectedComponentsMs !== null ? `${connectedComponentsMs}` : "N/A",
    ],
    ["Wire filtering ms", wireFilteringMs !== null ? `${wireFilteringMs}` : "N/A"],
    ["Line scan ms", lineScanMs !== null ? `${lineScanMs}` : "N/A"],
    ["Candidate scoring ms", candidateScoringMs !== null ? `${candidateScoringMs}` : "N/A"],
    ["Diagnostics ms", diagnosticsMs !== null ? `${diagnosticsMs}` : "N/A"],
    ["Detector total ms", detectorTotalMs !== null ? `${detectorTotalMs}` : "N/A"],
    ["Frame load ms", loadMs !== null ? `${loadMs}` : "N/A"],
    ["Preview encode ms", previewEncodeMs !== null ? `${previewEncodeMs}` : "N/A"],
    ["API total ms", apiTotalMs !== null ? `${apiTotalMs}` : "N/A"],
    ["Debug level", debugLevel ?? "N/A"],
  ];
  const detectorLimited =
    detectMs !== null && frameBudgetMs !== null && detectMs > 0.8 * frameBudgetMs;
  const previewLimited =
    previewEncodeMs !== null && frameBudgetMs !== null && previewEncodeMs > 0.3 * frameBudgetMs;
  const apiLimited =
    apiTotalMs !== null && frameBudgetMs !== null && apiTotalMs > frameBudgetMs && !detectorLimited;
  return (
    <section className="live-timing" aria-label="Live timing">
      <dl className="metric-list">
        {rows.map(([label, value]) => (
          <div key={label}>
            <dt>{label}</dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>
      {detectorLimited ? (
        <p className="panel-warning">
          Detector is slower than target FPS; playback is detector-limited.
        </p>
      ) : null}
      {previewLimited ? (
        <p className="panel-warning">
          Preview encoding is using a large share of the frame budget; playback is preview-limited.
        </p>
      ) : null}
      {apiLimited ? (
        <p className="panel-warning">
          API total time exceeds the frame budget; playback is network/api-limited.
        </p>
      ) : null}
    </section>
  );
}

function BatchRunControls({
  error,
  isBusy,
  measurementDefinition,
  onStart,
  onStop,
  runStatus,
  samplesLength,
}: {
  error: string | null;
  isBusy: boolean;
  measurementDefinition: MeasurementDefinition | null;
  onStart: () => void;
  onStop: () => void;
  runStatus: RunStatusResponse | null;
  samplesLength: number;
}) {
  return (
    <>
      <section className="panel-section">
        <h2>Controls</h2>
        <div className="button-row compact">
          <button
            className="primary"
            disabled={measurementDefinition === null || isBusy}
            onClick={onStart}
            type="button"
          >
            Start run
          </button>
          <button disabled={runStatus === null || isBusy} onClick={onStop} type="button">
            Stop run
          </button>
        </div>
      </section>

      <section className="panel-section">
        <h2>Definition</h2>
        <dl className="metric-list">
          <div>
            <dt>Target</dt>
            <dd>{measurementDefinition?.target_family ?? "-"}</dd>
          </div>
          <div>
            <dt>Frame</dt>
            <dd>
              {measurementDefinition
                ? `${measurementDefinition.acquisition_frame_size.width} x ${measurementDefinition.acquisition_frame_size.height}`
                : "-"}
            </dd>
          </div>
          <div>
            <dt>Run</dt>
            <dd>{runStatus?.run_id ?? "-"}</dd>
          </div>
          <div>
            <dt>Run status</dt>
            <dd>{runStatus?.status ?? "-"}</dd>
          </div>
          <div>
            <dt>Samples</dt>
            <dd>{runStatus?.sample_count ?? samplesLength}</dd>
          </div>
          <div>
            <dt>Temp source</dt>
            <dd>{String(runStatus?.temperature_source.source_type ?? "-")}</dd>
          </div>
          {error ? (
            <div className="metric-error">
              <dt>Error</dt>
              <dd>{error}</dd>
            </div>
          ) : null}
        </dl>
      </section>
    </>
  );
}

function LiveOfflineRunControls({
  currentIndex,
  datasetId,
  datasets,
  distance,
  error,
  errorKind,
  failedFrameIndex,
  fps,
  frameCount,
  frameName,
  isBusy,
  isPlaying,
  lastSuccessfulFrameIndex,
  loop,
  maxIndex,
  measurementDefinition,
  onClose,
  onDatasetChange,
  onFpsChange,
  onInspect,
  onLoopChange,
  onNext,
  onOpen,
  onPlayPause,
  onPrevious,
  onSeek,
  quality,
  relativeTimeS,
  state,
  status,
  temperatureC,
  temperatureSource,
  temperatureStatus,
  totalDurationS,
}: {
  currentIndex: number;
  datasetId: string;
  datasets: OfflineDataset[];
  distance: number | null;
  error: string | null;
  errorKind: string | null;
  failedFrameIndex: number | null;
  fps: number;
  frameCount: number;
  frameName: string | null;
  isBusy: boolean;
  isPlaying: boolean;
  lastSuccessfulFrameIndex: number | null;
  loop: boolean;
  maxIndex: number;
  measurementDefinition: MeasurementDefinition | null;
  onClose: () => void;
  onDatasetChange: (datasetId: string) => void;
  onFpsChange: (fps: number) => void;
  onInspect: () => void;
  onLoopChange: (loop: boolean) => void;
  onNext: () => void;
  onOpen: () => void;
  onPlayPause: () => void;
  onPrevious: () => void;
  onSeek: (frameIndex: number) => void;
  quality: number | null;
  relativeTimeS: number | null;
  state: string;
  status: string;
  temperatureC: number | null;
  temperatureSource: string | null;
  temperatureStatus: string | null;
  totalDurationS: number | null;
}) {
  const hasSession = frameCount > 0;

  return (
    <>
      <section className="panel-section">
        <h2>Live Offline Run</h2>
        <p className="panel-note">
          Pick a simulation material, or use YYT1771_AF_OFFLINE_DIR by default. The confirmed ROI
          and recipe stay locked. Set FPS before Open Live Source; during Play, detailed diagnostics
          overlays pause so playback can keep up with the target frame rate.
        </p>
        <OfflineDatasetSelector
          datasets={datasets}
          disabled={isBusy || hasSession}
          onChange={onDatasetChange}
          value={datasetId}
        />
        <div className="button-row compact">
          <button
            className="primary"
            disabled={measurementDefinition === null || isBusy}
            onClick={onOpen}
            type="button"
          >
            Open Live Source
          </button>
          <button disabled={!hasSession || isBusy} onClick={onClose} type="button">
            Close
          </button>
        </div>
      </section>

      <section className="panel-section two-column-fields">
        <label className="stacked-field">
          <span>FPS</span>
          <input
            min="1"
            onChange={(event) => onFpsChange(Number(event.currentTarget.value))}
            type="number"
            value={fps}
          />
        </label>
        <label className="inline-check">
          <input
            checked={loop}
            onChange={(event) => onLoopChange(event.currentTarget.checked)}
            type="checkbox"
          />
          <span>Loop</span>
        </label>
      </section>

      <section className="panel-section">
        <h2>Playback</h2>
        <div className="button-row horizontal">
          <button disabled={!hasSession || isBusy} onClick={onPrevious} type="button">
            Step Prev
          </button>
          <button
            className="primary"
            disabled={!hasSession}
            onClick={onPlayPause}
            type="button"
          >
            {isPlaying ? "Pause" : "Play"}
          </button>
          <button disabled={!hasSession || isBusy} onClick={onNext} type="button">
            Step Next
          </button>
        </div>
        <div className="button-row compact">
          <button disabled={!hasSession || isBusy} onClick={onInspect} type="button">
            Inspect current frame
          </button>
        </div>
        <label className="range-field">
          <span>Seek</span>
          <input
            aria-label="Live offline seek"
            disabled={!hasSession || isBusy}
            max={maxIndex}
            min="0"
            onChange={(event) => onSeek(Number(event.currentTarget.value))}
            type="range"
            value={currentIndex}
          />
        </label>
      </section>

      <section className="panel-section">
        <h2>Live Status</h2>
        <dl className="metric-list">
          <div>
            <dt>State</dt>
            <dd>{state}</dd>
          </div>
          <div>
            <dt>Frame index</dt>
            <dd>{hasSession ? `${currentIndex} / ${maxIndex}` : "N/A"}</dd>
          </div>
          <div>
            <dt>Last successful frame</dt>
            <dd>{lastSuccessfulFrameIndex === null ? "N/A" : lastSuccessfulFrameIndex}</dd>
          </div>
          <div>
            <dt>Failed frame</dt>
            <dd>{failedFrameIndex === null ? "N/A" : failedFrameIndex}</dd>
          </div>
          <div>
            <dt>Frame name</dt>
            <dd>{frameName ?? "N/A"}</dd>
          </div>
          <div>
            <dt>Material time</dt>
            <dd>
              {relativeTimeS === null || totalDurationS === null
                ? "N/A"
                : `${formatPlaybackTime(relativeTimeS)} / ${formatPlaybackTime(totalDurationS)}`}
            </dd>
          </div>
          <div>
            <dt>Relative time (s)</dt>
            <dd>{relativeTimeS === null ? "N/A" : relativeTimeS.toFixed(1)}</dd>
          </div>
          <div>
            <dt>Status</dt>
            <dd>{status}</dd>
          </div>
          <div>
            <dt>Distance</dt>
            <dd>{distance === null ? "N/A" : distance.toFixed(2)}</dd>
          </div>
          <div>
            <dt>Quality</dt>
            <dd>{quality === null ? "N/A" : quality.toFixed(2)}</dd>
          </div>
          <div>
            <dt>Temperature</dt>
            <dd>
              {temperatureC === null
                ? "N/A"
                : `${temperatureC.toFixed(1)}°C${temperatureStatus ? ` (${temperatureStatus})` : ""}${temperatureSource ? ` · ${temperatureSource}` : ""}`}
            </dd>
          </div>
          {state === "end_of_stream" ? (
            <div className="metric-error">
              <dt>End</dt>
              <dd>end_of_stream</dd>
            </div>
          ) : null}
          {error ? (
            <div className="metric-error">
              <dt>{errorKind ?? "Error"}</dt>
              <dd>{error}</dd>
            </div>
          ) : null}
        </dl>
      </section>
    </>
  );
}

function frameRefFromOfflineRunFrame(frame: OfflineRunFrame | null): FrameRef | null {
  if (frame === null) {
    return null;
  }
  return {
    frame_id: frame.frame_index + 1,
    timestamp_ms: Math.round(frame.relative_time_s * 1000),
    width: frame.acquisition_width,
    height: frame.acquisition_height,
    coordinate_space: "acquisition",
  };
}

function cameraStatusFromOfflineRunFrame(
  frame: OfflineRunFrame | null,
  opened: boolean,
): CameraStatus | null {
  if (!opened) {
    return null;
  }
  return {
    opened: true,
    source_type: "offline",
    latest_frame_id: frame ? frame.frame_index + 1 : null,
    frame_width: frame?.acquisition_width ?? null,
    frame_height: frame?.acquisition_height ?? null,
    coordinate_space: "acquisition",
  };
}
