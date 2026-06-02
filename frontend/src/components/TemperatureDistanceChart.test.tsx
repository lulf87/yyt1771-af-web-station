import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import type { TemperatureDistanceSample } from "../run/temperatureDistanceSeries";
import { TemperatureDistanceChart } from "./TemperatureDistanceChart";

const samples: TemperatureDistanceSample[] = [
  {
    frameIndex: 1,
    relativeTimeS: 0.1,
    temperatureC: 40,
    distancePx: 100,
    status: "ok",
    quality: 0.95,
    valid: true,
  },
  {
    frameIndex: 2,
    relativeTimeS: 0.2,
    temperatureC: 41,
    distancePx: 130,
    status: "ok",
    quality: 0.55,
    valid: true,
  },
  {
    frameIndex: 3,
    relativeTimeS: 0.3,
    temperatureC: 42,
    distancePx: null,
    status: "target_not_found",
    quality: 0.2,
    valid: false,
  },
];

describe("TemperatureDistanceChart", () => {
  it("renders distance vs time by default with line segments, latest point, jump marker, and tooltip text", () => {
    const markup = renderToStaticMarkup(
      <TemperatureDistanceChart
        jumpThresholdPx={20}
        onClear={() => undefined}
        samples={samples}
      />,
    );

    expect(markup).toContain("间距-时间实时曲线");
    expect(markup).toContain("Distance vs Time");
    expect(markup).toContain("Time (s)");
    expect(markup).toContain("distance_px");
    expect(markup).toContain("chart-distance-line");
    expect(markup).toContain("chart-sample-point");
    expect(markup).toContain("chart-invalid-point");
    expect(markup).toContain("chart-current-point");
    expect(markup).toContain("chart-jump-marker");
    expect(markup).toContain("Frame 2");
    expect(markup).toContain("temperature: 41.00 °C");
    expect(markup).toContain("distance: 130.00 px");
    expect(markup).toContain("status: ok");
    expect(markup).toContain("quality: 0.55");
    expect(markup).toContain("time: 0.2s");
    expect(markup).toContain("Clear chart");
  });

  it("renders temperature vs distance as scatter plus binned trend instead of a sample-order line", () => {
    const repeatedTemperatureSamples: TemperatureDistanceSample[] = [
      {
        frameIndex: 1,
        relativeTimeS: 0.1,
        temperatureC: 40.01,
        distancePx: 100,
        status: "ok",
        quality: 0.95,
        valid: true,
      },
      {
        frameIndex: 2,
        relativeTimeS: 0.2,
        temperatureC: 40.04,
        distancePx: 104,
        status: "ok",
        quality: 0.95,
        valid: true,
      },
      {
        frameIndex: 3,
        relativeTimeS: 0.3,
        temperatureC: 40.17,
        distancePx: 120,
        status: "ok",
        quality: 0.95,
        valid: true,
      },
    ];

    const markup = renderToStaticMarkup(
      <TemperatureDistanceChart
        initialMode="temperature_distance"
        onClear={() => undefined}
        samples={repeatedTemperatureSamples}
      />,
    );

    expect(markup).toContain("温度-间距关系");
    expect(markup).toContain("Temperature vs Distance");
    expect(markup).toContain("原始点以散点显示");
    expect(markup).toContain("chart-scatter-point");
    expect(markup).toContain("chart-trend-line");
    expect(markup).toContain("chart-trend-point");
    expect(markup).not.toContain("chart-distance-line");
    expect(markup).toContain("bin count: 2");
    expect(markup).toContain("mean distance: 102.00 px");
  });
});
