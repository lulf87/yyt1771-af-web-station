import { useEffect, useMemo, useState } from "react";

import {
  nextOfflinePlayback,
  openOfflinePlayback,
  previousOfflinePlayback,
  seekOfflinePlayback,
} from "../api/client";
import type {
  FrameRef,
  MeasurementDefinition,
  OfflineDataset,
  OfflinePlaybackFrame,
  OfflinePlaybackStatus,
  RotatedRoi,
  TargetFamily,
} from "../api/types";
import { FrameCanvas } from "../components/FrameCanvas";
import { OfflineDatasetSelector } from "../components/OfflineDatasetSelector";
import { StatusPanel } from "../components/StatusPanel";
import { TargetFamilySelector } from "../components/TargetFamilySelector";

interface PlaybackPageProps {
  datasets: OfflineDataset[];
  datasetId: string;
  onDatasetChange: (datasetId: string) => void;
  measurementDefinition: MeasurementDefinition | null;
}

const defaultRoi: RotatedRoi = {
  center_x: 1024,
  center_y: 682,
  width: 800,
  height: 300,
  angle_deg: 0,
  coordinate_space: "acquisition",
};

export function PlaybackPage({
  datasets,
  datasetId,
  onDatasetChange,
  measurementDefinition,
}: PlaybackPageProps) {
  const [framesDir, setFramesDir] = useState("");
  const [evaluationDir, setEvaluationDir] = useState("");
  const [datasetLabel, setDatasetLabel] = useState("");
  const [targetFamily, setTargetFamily] = useState<TargetFamily>(
    measurementDefinition?.target_family ?? "balloon_envelope",
  );
  const [fps, setFps] = useState(10);
  const [maxPreviewWidth, setMaxPreviewWidth] = useState(1200);
  const [status, setStatus] = useState<OfflinePlaybackStatus | null>(null);
  const [frame, setFrame] = useState<OfflinePlaybackFrame | null>(null);
  const [failuresOnly, setFailuresOnly] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const roi = measurementDefinition?.roi ?? defaultRoi;
  const frameRef = useMemo<FrameRef | null>(() => {
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
  }, [frame]);

  useEffect(() => {
    if (!isPlaying) {
      return undefined;
    }
    const timer = window.setInterval(() => {
      void stepNext();
    }, Math.max(60, 1000 / Math.max(1, fps)));
    return () => window.clearInterval(timer);
  });

  async function handleOpen() {
    await runAction("open-playback", async () => {
      const opened = await openOfflinePlayback({
        frames_dir: framesDir.trim() || null,
        dataset_id: framesDir.trim() ? null : datasetId || null,
        evaluation_output_dir: evaluationDir.trim() || null,
        dataset_label: datasetLabel.trim() || null,
        target_family: targetFamily,
        roi,
        fps,
        recipe_name: measurementDefinition?.recipe_name ?? null,
        max_preview_width: maxPreviewWidth,
      });
      setStatus(opened);
      setFrame(opened.current);
      setIsPlaying(false);
    });
  }

  async function handleSeek(frameIndex: number) {
    await runAction("seek", async () => {
      setFrame(await seekOfflinePlayback(frameIndex));
    });
  }

  async function stepNext() {
    await runAction("next", async () => {
      const nextFrame = await nextOfflinePlayback(failuresOnly);
      setFrame(nextFrame);
    });
  }

  async function stepPrevious() {
    await runAction("previous", async () => {
      const previousFrame = await previousOfflinePlayback(failuresOnly);
      setFrame(previousFrame);
    });
  }

  async function runAction(action: string, task: () => Promise<void>) {
    setBusyAction(action);
    setError(null);
    try {
      await task();
    } catch (caughtError) {
      setIsPlaying(false);
      setError(caughtError instanceof Error ? caughtError.message : "Request failed.");
    } finally {
      setBusyAction(null);
    }
  }

  const isBusy = busyAction !== null;
  const currentIndex = frame?.frame_index ?? 0;
  const maxIndex = Math.max(0, (status?.frame_count ?? 1) - 1);
  const jumpFrames = status?.top_jump_frames ?? [];
  const failureCount = status?.failure_frame_indices.length ?? 0;

  return (
    <main className="app-shell">
      <header className="top-bar">
        <div>
          <h1>YYT1771 AF Web Station</h1>
          <p>Offline Playback</p>
        </div>
        <div className="source-pill">
          {status?.opened ? `${status.mode} playback` : "playback closed"}
        </div>
      </header>

      <section className="playback-grid" aria-label="Offline playback workspace">
        <section className="frame-stage" aria-label="Playback frame">
          <FrameCanvas
            detection={frame?.detection ?? null}
            emptyLabel="Open offline playback to show frames"
            frameRef={frameRef}
            previewUrl={frame?.preview_url ?? null}
            roi={roi}
          />
        </section>

        <aside className="setup-panel" aria-label="Playback controls">
          <section className="panel-section">
            <h2>Source</h2>
            <OfflineDatasetSelector
              datasets={datasets}
              disabled={isBusy}
              onChange={onDatasetChange}
              value={datasetId}
            />
            <label className="stacked-field">
              <span>Frames dir (overrides material)</span>
              <input
                onChange={(event) => setFramesDir(event.currentTarget.value)}
                placeholder="YYT1771_AF_OFFLINE_DIR"
                value={framesDir}
              />
            </label>
            <label className="stacked-field">
              <span>Evaluation dir</span>
              <input
                onChange={(event) => setEvaluationDir(event.currentTarget.value)}
                placeholder="validation_results/offline_eval..."
                value={evaluationDir}
              />
            </label>
            <label className="stacked-field">
              <span>Dataset label</span>
              <input
                onChange={(event) => setDatasetLabel(event.currentTarget.value)}
                placeholder="local label"
                value={datasetLabel}
              />
            </label>
          </section>

          <section className="panel-section">
            <h2>Target</h2>
            <TargetFamilySelector value={targetFamily} onChange={setTargetFamily} />
          </section>

          <section className="panel-section two-column-fields">
            <label className="stacked-field">
              <span>FPS</span>
              <input
                min="1"
                onChange={(event) => setFps(Number(event.currentTarget.value))}
                type="number"
                value={fps}
              />
            </label>
            <label className="stacked-field">
              <span>Preview width</span>
              <input
                min="160"
                onChange={(event) => setMaxPreviewWidth(Number(event.currentTarget.value))}
                type="number"
                value={maxPreviewWidth}
              />
            </label>
          </section>

          <section className="panel-section">
            <h2>Timeline</h2>
            <input
              aria-label="Playback timeline"
              disabled={status === null || isBusy}
              max={maxIndex}
              min="0"
              onChange={(event) => {
                void handleSeek(Number(event.currentTarget.value));
              }}
              type="range"
              value={currentIndex}
            />
            <dl className="metric-list compact-metrics">
              <div>
                <dt>Frame</dt>
                <dd>{frame ? `${frame.frame_index} / ${maxIndex}` : "N/A"}</dd>
              </div>
              <div>
                <dt>Time</dt>
                <dd>{frame ? `${frame.relative_time_s.toFixed(3)} s` : "N/A"}</dd>
              </div>
              <div>
                <dt>Failures</dt>
                <dd>{failureCount}</dd>
              </div>
            </dl>
          </section>

          <section className="panel-section">
            <h2>Result</h2>
            <StatusPanel cameraStatus={null} detection={frame?.detection ?? null} error={error} />
          </section>

          <section className="panel-section">
            <h2>Top jumps</h2>
            <div className="jump-button-list">
              {jumpFrames.length === 0 ? <span className="muted-text">N/A</span> : null}
              {jumpFrames.slice(0, 8).map((frameIndex) => (
                <button
                  disabled={isBusy}
                  key={frameIndex}
                  onClick={() => {
                    void handleSeek(frameIndex);
                  }}
                  type="button"
                >
                  {frameIndex}
                </button>
              ))}
            </div>
          </section>

          <div className="button-row">
            <button disabled={isBusy} onClick={handleOpen} type="button">
              Open playback
            </button>
            <div className="button-row horizontal">
              <button disabled={status === null || isBusy} onClick={stepPrevious} type="button">
                Prev
              </button>
              <button
                className="primary"
                disabled={status === null || isBusy}
                onClick={() => setIsPlaying((value) => !value)}
                type="button"
              >
                {isPlaying ? "Pause" : "Play"}
              </button>
              <button disabled={status === null || isBusy} onClick={stepNext} type="button">
                Next
              </button>
            </div>
            <label className="inline-check">
              <input
                checked={failuresOnly}
                onChange={(event) => setFailuresOnly(event.currentTarget.checked)}
                type="checkbox"
              />
              <span>Failures only</span>
            </label>
          </div>
        </aside>
      </section>
    </main>
  );
}
