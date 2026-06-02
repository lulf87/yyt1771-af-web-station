import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { SetupPage } from "./SetupPage";

describe("SetupPage collapsed panels", () => {
  it("folds recipe and result panels and removes the manual detection button", () => {
    const markup = renderToStaticMarkup(
      <SetupPage
        datasets={[]}
        datasetId=""
        onDatasetChange={() => {}}
        onMeasurementDefinitionConfirmed={() => {}}
      />,
    );

    expect(markup).toContain("<summary><h2>Recipe summary</h2></summary>");
    expect(markup).toContain("<summary><h2>Result</h2></summary>");
    expect(markup).not.toContain("Run detection");
  });

  it("exposes ROI angle for auto-refreshing detection after rotation edits", () => {
    const markup = renderToStaticMarkup(
      <SetupPage
        datasets={[]}
        datasetId=""
        onDatasetChange={() => {}}
        onMeasurementDefinitionConfirmed={() => {}}
      />,
    );

    expect(markup).toContain("Angle");
  });

  it("exposes raw-only crop zoom and point probe controls", () => {
    const markup = renderToStaticMarkup(
      <SetupPage
        datasets={[]}
        datasetId=""
        onDatasetChange={() => {}}
        onMeasurementDefinitionConfirmed={() => {}}
      />,
    );

    expect(markup).toContain("Raw only");
    expect(markup).toContain("Probe point");
    expect(markup).toContain("ROI crop zoom");
  });
});
