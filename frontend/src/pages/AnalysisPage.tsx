import { useEffect, useMemo, useState } from "react";

import { downloadRunExport, listRuns, postRunAnalysis } from "../api/client";
import type { AnalysisResponse, ExportFormat, RunSummary } from "../api/types";
import { af95Label, analysisSummaryRows } from "../analysis/analysisDisplay";

export function AnalysisPage() {
  const [runs, setRuns] = useState<RunSummary[]>([]);
  const [selectedRunId, setSelectedRunId] = useState("");
  const [analysis, setAnalysis] = useState<AnalysisResponse | null>(null);
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void refreshRuns();
  }, []);

  const summaryRows = analysisSummaryRows(analysis);
  const curvePath = useMemo(() => buildCurvePath(analysis), [analysis]);

  async function refreshRuns() {
    await runAction("runs", async () => {
      const payload = await listRuns();
      setRuns(payload.runs);
      if (selectedRunId === "" && payload.runs.length > 0) {
        setSelectedRunId(payload.runs[0].run_id);
      }
    });
  }

  async function handleAnalyze() {
    if (selectedRunId === "") {
      setError("Select a run first.");
      return;
    }
    await runAction("analysis", async () => {
      setAnalysis(await postRunAnalysis(selectedRunId));
    });
  }

  async function handleDownload(format: ExportFormat) {
    if (selectedRunId === "") {
      setError("Select a run first.");
      return;
    }
    await runAction(`export-${format}`, async () => {
      await downloadRunExport(selectedRunId, format);
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
          <p>Analysis</p>
        </div>
        <div className="source-pill">{selectedRunId || "no run selected"}</div>
      </header>

      <section className="analysis-grid" aria-label="Analysis workspace">
        <section className="analysis-main">
          <div className="analysis-toolbar">
            <select
              aria-label="Run"
              onChange={(event) => {
                setSelectedRunId(event.target.value);
                setAnalysis(null);
              }}
              value={selectedRunId}
            >
              <option value="">Select run</option>
              {runs.map((run) => (
                <option key={run.run_id} value={run.run_id}>
                  {run.run_id}
                </option>
              ))}
            </select>
            <button disabled={isBusy} onClick={refreshRuns} type="button">
              Refresh
            </button>
            <button
              className="primary"
              disabled={selectedRunId === "" || isBusy}
              onClick={handleAnalyze}
              type="button"
            >
              Analyze
            </button>
          </div>

          <div className="analysis-chart" aria-label="Temperature distance curve">
            {curvePath ? (
              <svg viewBox="0 0 640 260" role="img" aria-label="temperature distance curve">
                <path className="curve-grid" d="M48 24 V220 H612" />
                <path className="curve-line" d={curvePath} />
              </svg>
            ) : (
              <div className="chart-empty">No analysis curve</div>
            )}
          </div>
        </section>

        <aside className="setup-panel" aria-label="Analysis result">
          <section className="panel-section">
            <h2>Af-95</h2>
            <div className="af-value">{af95Label(analysis)}</div>
          </section>

          <section className="panel-section">
            <h2>Result</h2>
            <dl className="metric-list">
              {summaryRows.map((row) => (
                <div key={row.label}>
                  <dt>{row.label}</dt>
                  <dd>{row.value}</dd>
                </div>
              ))}
              {error ? (
                <div className="metric-error">
                  <dt>Error</dt>
                  <dd>{error}</dd>
                </div>
              ) : null}
            </dl>
          </section>

          <section className="panel-section">
            <h2>Exports</h2>
            <div className="export-grid">
              {(["csv", "json", "png", "xlsx"] as const).map((format) => (
                <button
                  disabled={selectedRunId === "" || isBusy}
                  key={format}
                  onClick={() => void handleDownload(format)}
                  type="button"
                >
                  {format.toUpperCase()}
                </button>
              ))}
            </div>
          </section>

          <section className="panel-section">
            <h2>Diagnostics</h2>
            <dl className="metric-list">
              {analysis === null || Object.keys(analysis.diagnostics).length === 0 ? (
                <div>
                  <dt>Reason</dt>
                  <dd>-</dd>
                </div>
              ) : (
                Object.entries(analysis.diagnostics).map(([key, value]) => (
                  <div key={key}>
                    <dt>{key}</dt>
                    <dd>{String(value)}</dd>
                  </div>
                ))
              )}
            </dl>
          </section>
        </aside>
      </section>
    </main>
  );
}

function buildCurvePath(analysis: AnalysisResponse | null): string {
  const points = analysis?.curve ?? [];
  if (points.length === 0) {
    return "";
  }

  const temperatures = points.map((point) => point.temperature_c);
  const distances = points.map((point) => point.distance_px);
  const minTemperature = Math.min(...temperatures);
  const maxTemperature = Math.max(...temperatures);
  const minDistance = Math.min(...distances);
  const maxDistance = Math.max(...distances);
  const width = 564;
  const height = 196;
  const left = 48;
  const bottom = 220;

  return points
    .map((point, index) => {
      const x =
        left +
        normalize(point.temperature_c, minTemperature, maxTemperature) * width;
      const y =
        bottom -
        normalize(point.distance_px, minDistance, maxDistance) * height;
      return `${index === 0 ? "M" : "L"} ${x.toFixed(1)} ${y.toFixed(1)}`;
    })
    .join(" ");
}

function normalize(value: number, min: number, max: number): number {
  if (Math.abs(max - min) < 1e-9) {
    return 0.5;
  }
  return (value - min) / (max - min);
}
