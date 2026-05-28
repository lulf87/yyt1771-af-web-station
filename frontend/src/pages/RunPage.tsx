import { useState } from "react";

import { getRunSamples, getRunStatus, startRun, stopRun } from "../api/client";
import type { MeasurementDefinition, RunSample, RunStatusResponse } from "../api/types";
import { FrameCanvas } from "../components/FrameCanvas";
import { TemperaturePanel } from "../components/TemperaturePanel";
import { latestSample, sampleRows } from "../run/sampleDisplay";

interface RunPageProps {
  measurementDefinition: MeasurementDefinition | null;
}

const fallbackRoi = {
  center_x: 1,
  center_y: 1,
  width: 1,
  height: 1,
  angle_deg: 0,
  coordinate_space: "acquisition" as const,
};

export function RunPage({ measurementDefinition }: RunPageProps) {
  const [runStatus, setRunStatus] = useState<RunStatusResponse | null>(null);
  const [samples, setSamples] = useState<RunSample[]>([]);
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const latest = latestSample(samples);
  const latestFrameRef = latest?.detection.frame_ref ?? null;
  const latestPreviewUrl =
    latestFrameRef === null
      ? null
      : `/api/camera/frame/${latestFrameRef.frame_id}/preview.png?max_width=1200`;
  const rows = sampleRows(samples).slice(-12).reverse();
  const chartSamples = samples.slice(-24);
  const maxDistance = Math.max(
    1,
    ...chartSamples.map((sample) => sample.detection.distance_px ?? 0),
  );

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
                {latest?.detection.distance_px === null || !latest
                  ? "-"
                  : latest.detection.distance_px.toFixed(2)}
              </strong>
            </div>
            <div className="summary-tile">
              <span>Status</span>
              <strong>{latest?.detection.status ?? "waiting"}</strong>
            </div>
            <div className="summary-tile">
              <span>Quality</span>
              <strong>{latest ? latest.detection.quality.toFixed(2) : "-"}</strong>
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
              detection={latest?.detection ?? null}
              emptyLabel="Start a run to show the latest frame"
              frameRef={latestFrameRef}
              previewUrl={latestPreviewUrl}
              roi={measurementDefinition?.roi ?? fallbackRoi}
            />
          </section>
        </section>

        <aside className="setup-panel" aria-label="Run controls">
          <TemperaturePanel />

          <section className="panel-section">
            <h2>Controls</h2>
            <div className="button-row compact">
              <button
                className="primary"
                disabled={measurementDefinition === null || isBusy}
                onClick={handleStart}
                type="button"
              >
                Start run
              </button>
              <button disabled={runStatus === null || isBusy} onClick={handleStop} type="button">
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
                <dt>Samples</dt>
                <dd>{runStatus?.sample_count ?? samples.length}</dd>
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
