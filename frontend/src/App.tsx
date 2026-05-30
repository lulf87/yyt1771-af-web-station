import { useEffect, useState } from "react";

import { listOfflineDatasets } from "./api/client";
import type { MeasurementDefinition, OfflineDataset } from "./api/types";
import { AnalysisPage } from "./pages/AnalysisPage";
import { PlaybackPage } from "./pages/PlaybackPage";
import { RunPage } from "./pages/RunPage";
import { SetupPage } from "./pages/SetupPage";

type Page = "setup" | "run" | "playback" | "analysis";

export default function App() {
  const [page, setPage] = useState<Page>("setup");
  const [measurementDefinition, setMeasurementDefinition] =
    useState<MeasurementDefinition | null>(null);
  const [datasets, setDatasets] = useState<OfflineDataset[]>([]);
  const [datasetId, setDatasetId] = useState("");

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const available = await listOfflineDatasets();
        if (cancelled) {
          return;
        }
        setDatasets(available);
        const firstAvailable = available.find((dataset) => dataset.available);
        if (firstAvailable) {
          setDatasetId(firstAvailable.dataset_id);
        }
      } catch {
        if (!cancelled) {
          setDatasets([]);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  function handleMeasurementDefinitionConfirmed(nextDefinition: MeasurementDefinition) {
    setMeasurementDefinition(nextDefinition);
    setPage("run");
  }

  return (
    <>
      <nav className="app-nav" aria-label="Application sections">
        <button
          aria-pressed={page === "setup"}
          className={page === "setup" ? "nav-button active" : "nav-button"}
          onClick={() => setPage("setup")}
          type="button"
        >
          Setup
        </button>
        <button
          aria-pressed={page === "run"}
          className={page === "run" ? "nav-button active" : "nav-button"}
          onClick={() => setPage("run")}
          type="button"
        >
          Run
        </button>
        <button
          aria-pressed={page === "playback"}
          className={page === "playback" ? "nav-button active" : "nav-button"}
          onClick={() => setPage("playback")}
          type="button"
        >
          Playback
        </button>
        <button
          aria-pressed={page === "analysis"}
          className={page === "analysis" ? "nav-button active" : "nav-button"}
          onClick={() => setPage("analysis")}
          type="button"
        >
          Analysis
        </button>
      </nav>
      {page === "setup" ? (
        <SetupPage
          datasets={datasets}
          datasetId={datasetId}
          onDatasetChange={setDatasetId}
          onMeasurementDefinitionConfirmed={handleMeasurementDefinitionConfirmed}
        />
      ) : page === "run" ? (
        <RunPage
          datasets={datasets}
          datasetId={datasetId}
          measurementDefinition={measurementDefinition}
          onDatasetChange={setDatasetId}
        />
      ) : page === "playback" ? (
        <PlaybackPage
          datasets={datasets}
          datasetId={datasetId}
          measurementDefinition={measurementDefinition}
          onDatasetChange={setDatasetId}
        />
      ) : (
        <AnalysisPage />
      )}
    </>
  );
}
