import { useState } from "react";

import type { MeasurementDefinition } from "./api/types";
import { AnalysisPage } from "./pages/AnalysisPage";
import { PlaybackPage } from "./pages/PlaybackPage";
import { RunPage } from "./pages/RunPage";
import { SetupPage } from "./pages/SetupPage";

type Page = "setup" | "run" | "playback" | "analysis";

export default function App() {
  const [page, setPage] = useState<Page>("setup");
  const [measurementDefinition, setMeasurementDefinition] =
    useState<MeasurementDefinition | null>(null);

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
        <SetupPage onMeasurementDefinitionConfirmed={handleMeasurementDefinitionConfirmed} />
      ) : page === "run" ? (
        <RunPage measurementDefinition={measurementDefinition} />
      ) : page === "playback" ? (
        <PlaybackPage measurementDefinition={measurementDefinition} />
      ) : (
        <AnalysisPage />
      )}
    </>
  );
}
