import { useEffect, useRef, useState } from "react";

import {
  closeOfflineRun,
  getRunSamples,
  getRunStatus,
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
  OfflineRunFrame,
  OfflineRunOpenResponse,
  RunSample,
  RunStatusResponse,
} from "../api/types";
import { FrameCanvas } from "../components/FrameCanvas";
import { StatusPanel } from "../components/StatusPanel";
import { TemperaturePanel } from "../components/TemperaturePanel";
import { latestSample, sampleRows } from "../run/sampleDisplay";

interface RunPageProps {
  measurementDefinition: MeasurementDefinition | null;
}

type RunMode = "batch" | "live_offline";

const fallbackRoi = {
  center_x: 1,
  center_y: 1,
  width: 1,
  height: 1,
  angle_deg: 0,
  coordinate_space: "acquisition" as const,
};

export function RunPage({ measurementDefinition }: RunPageProps) {
  const [runMode, setRunMode] = useState<RunMode>("live_offline");
  const [runStatus, setRunStatus] = useState<RunStatusResponse | null>(null);
  const [samples, setSamples] = useState<RunSample[]>([]);
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [offlineRun, setOfflineRun] = useState<OfflineRunOpenResponse | null>(null);
  const [liveFrame, setLiveFrame] = useState<OfflineRunFrame | null>(null);
  const [liveFps, setLiveFps] = useState(10);
  const [liveLoop, setLiveLoop] = useState(true);
  const [isLivePlaying, setIsLivePlaying] = useState(false);
  const inFlightLiveRequest = useRef(false);
  const liveTimer = useRef<number | null>(null);

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
  const liveState =
    offlineRun === null
      ? "unopened"
      : liveFrame?.end_of_stream
        ? "end_of_stream"
        : isLivePlaying
          ? "playing"
          : "paused";

  useEffect(() => {
    if (!isLivePlaying || offlineRun === null) {
      return undefined;
    }

    let cancelled = false;
    const schedule = (delayMs: number) => {
      liveTimer.current = window.setTimeout(() => {
        void tick();
      }, delayMs);
    };
    const tick = async () => {
      if (cancelled) {
        return;
      }
      const startedAt = Date.now();
      const frame = await advanceLiveNext({ fromPlaybackLoop: true });
      if (cancelled || frame?.end_of_stream) {
        return;
      }
      const elapsedMs = Date.now() - startedAt;
      schedule(Math.max(20, 1000 / Math.max(1, liveFps) - elapsedMs));
    };

    schedule(0);
    return () => {
      cancelled = true;
      if (liveTimer.current !== null) {
        window.clearTimeout(liveTimer.current);
        liveTimer.current = null;
      }
    };
  }, [isLivePlaying, offlineRun?.session_id, liveFps]);

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
        fps: liveFps,
        loop: liveLoop,
        dataset_label: null,
        start_frame_index: 0,
        max_preview_width: 1200,
      });
      setOfflineRun(opened);
      setIsLivePlaying(false);
      const firstFrame = await nextOfflineRun(opened.session_id);
      setLiveFrame(firstFrame);
    });
  }

  async function handleCloseLive() {
    if (offlineRun === null) {
      return;
    }
    await runAction("close-live", async () => {
      setIsLivePlaying(false);
      await closeOfflineRun(offlineRun.session_id);
      setOfflineRun(null);
      setLiveFrame(null);
    });
  }

  async function handleLivePrevious() {
    if (offlineRun === null) {
      return;
    }
    await runAction("live-previous", async () => {
      setLiveFrame(await previousOfflineRun(offlineRun.session_id));
    });
  }

  async function handleLiveNext() {
    await advanceLiveNext({ fromPlaybackLoop: false });
  }

  async function handleLiveSeek(frameIndex: number) {
    if (offlineRun === null) {
      return;
    }
    await runAction("live-seek", async () => {
      setIsLivePlaying(false);
      setLiveFrame(await seekOfflineRun(offlineRun.session_id, frameIndex));
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
    try {
      const frame = await nextOfflineRun(offlineRun.session_id);
      setLiveFrame(frame);
      if (frame.end_of_stream) {
        setIsLivePlaying(false);
      }
      return frame;
    } catch (caughtError) {
      setIsLivePlaying(false);
      setError(caughtError instanceof Error ? caughtError.message : "Request failed.");
      return null;
    } finally {
      inFlightLiveRequest.current = false;
      if (!fromPlaybackLoop) {
        setBusyAction(null);
      }
    }
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

  const isBusy = busyAction !== null;
  const frameCount = offlineRun?.frame_count ?? 0;
  const maxLiveIndex = Math.max(0, frameCount - 1);
  const currentLiveIndex = liveFrame?.frame_index ?? offlineRun?.current_frame_index ?? 0;

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
            <div className="summary-tile">
              <span>Temperature</span>
              <strong>
                {latest?.temperature_c === null || !latest ? "-" : latest.temperature_c.toFixed(1)}
              </strong>
            </div>

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
              previewUrl={activePreviewUrl}
              roi={measurementDefinition?.roi ?? fallbackRoi}
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
                  setRunMode("batch");
                  setIsLivePlaying(false);
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
              distance={activeDetection?.distance_px ?? null}
              error={error}
              fps={liveFps}
              frameCount={frameCount}
              isBusy={isBusy}
              isPlaying={isLivePlaying}
              loop={liveLoop}
              maxIndex={maxLiveIndex}
              measurementDefinition={measurementDefinition}
              onClose={handleCloseLive}
              onFpsChange={setLiveFps}
              onLoopChange={setLiveLoop}
              onNext={handleLiveNext}
              onOpen={handleOpenLive}
              onPlayPause={() => setIsLivePlaying((value) => !value)}
              onPrevious={handleLivePrevious}
              onSeek={handleLiveSeek}
              quality={activeDetection?.quality ?? null}
              state={liveState}
              status={activeDetection?.status ?? "waiting"}
            />
          )}

          {runMode === "live_offline" ? (
            <section className="panel-section">
              <h2>Diagnostics</h2>
              <StatusPanel
                cameraStatus={liveCameraStatus}
                detection={activeDetection}
                error={error}
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
  distance,
  error,
  fps,
  frameCount,
  isBusy,
  isPlaying,
  loop,
  maxIndex,
  measurementDefinition,
  onClose,
  onFpsChange,
  onLoopChange,
  onNext,
  onOpen,
  onPlayPause,
  onPrevious,
  onSeek,
  quality,
  state,
  status,
}: {
  currentIndex: number;
  distance: number | null;
  error: string | null;
  fps: number;
  frameCount: number;
  isBusy: boolean;
  isPlaying: boolean;
  loop: boolean;
  maxIndex: number;
  measurementDefinition: MeasurementDefinition | null;
  onClose: () => void;
  onFpsChange: (fps: number) => void;
  onLoopChange: (loop: boolean) => void;
  onNext: () => void;
  onOpen: () => void;
  onPlayPause: () => void;
  onPrevious: () => void;
  onSeek: (frameIndex: number) => void;
  quality: number | null;
  state: string;
  status: string;
}) {
  const hasSession = frameCount > 0;

  return (
    <>
      <section className="panel-section">
        <h2>Live Offline Run</h2>
        <p className="panel-note">
          Uses YYT1771_AF_OFFLINE_DIR by default and locks the confirmed ROI and recipe.
        </p>
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
          {state === "end_of_stream" ? (
            <div className="metric-error">
              <dt>End</dt>
              <dd>end_of_stream</dd>
            </div>
          ) : null}
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
