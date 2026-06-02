import { useMemo, useState } from "react";

import type {
  DistanceTimePoint,
  TemperatureDistanceBin,
  TemperatureDistanceSample,
} from "../run/temperatureDistanceSeries";
import {
  buildDistanceTimeLineSegments,
  buildTemperatureDistanceBins,
  buildTemperatureDistanceScatter,
  distanceTimeDomains,
  distanceTimeXValue,
  isDistanceTimePoint,
  temperatureDistanceDomains,
} from "../run/temperatureDistanceSeries";
import { formatPlaybackTime } from "../run/liveOfflineDisplay";

type ChartMode = "distance_time" | "temperature_distance";

interface TemperatureDistanceChartProps {
  samples: TemperatureDistanceSample[];
  onClear: () => void;
  jumpThresholdPx?: number;
  initialMode?: ChartMode;
}

interface ChartLayout {
  width: number;
  height: number;
  padding: number;
}

interface SampleChartPoint {
  sample: TemperatureDistanceSample;
  x: number;
  y: number;
}

interface TrendChartPoint {
  bin: TemperatureDistanceBin;
  x: number;
  y: number;
}

const defaultLayout: ChartLayout = {
  width: 720,
  height: 300,
  padding: 46,
};

const defaultJumpThresholdPx = 25;
const lowConfidenceBinCount = 2;

export function TemperatureDistanceChart({
  samples,
  onClear,
  jumpThresholdPx = defaultJumpThresholdPx,
  initialMode = "distance_time",
}: TemperatureDistanceChartProps) {
  const [mode, setMode] = useState<ChartMode>(initialMode);
  const view = useMemo(
    () =>
      mode === "distance_time"
        ? buildDistanceTimeView(samples, jumpThresholdPx)
        : buildTemperatureDistanceView(samples, jumpThresholdPx),
    [jumpThresholdPx, mode, samples],
  );

  return (
    <section className="temperature-distance-panel" aria-label="Temperature distance chart">
      <header className="chart-header">
        <div>
          <h2>{view.title}</h2>
          <p className="chart-subtitle">{view.subtitle}</p>
        </div>
        <div className="chart-actions">
          <div aria-label="Chart mode" className="chart-mode-toggle" role="group">
            <button
              aria-pressed={mode === "distance_time"}
              className={mode === "distance_time" ? "active" : ""}
              onClick={() => setMode("distance_time")}
              type="button"
            >
              Distance vs Time
            </button>
            <button
              aria-pressed={mode === "temperature_distance"}
              className={mode === "temperature_distance" ? "active" : ""}
              onClick={() => setMode("temperature_distance")}
              type="button"
            >
              Temperature vs Distance
            </button>
          </div>
          <button disabled={samples.length === 0} onClick={onClear} type="button">
            Clear chart
          </button>
        </div>
      </header>
      <svg
        aria-label={view.subtitle}
        className="temperature-distance-chart"
        role="img"
        viewBox={`0 0 ${defaultLayout.width} ${defaultLayout.height}`}
      >
        <rect
          className="chart-plot-bg"
          height={plotHeight(defaultLayout)}
          width={plotWidth(defaultLayout)}
          x={defaultLayout.padding}
          y={defaultLayout.padding / 2}
        />
        {renderTicks(view.domains.x, "x")}
        {renderTicks(view.domains.y, "y")}
        <line
          className="chart-axis"
          x1={defaultLayout.padding}
          x2={defaultLayout.width - defaultLayout.padding / 2}
          y1={defaultLayout.height - defaultLayout.padding}
          y2={defaultLayout.height - defaultLayout.padding}
        />
        <line
          className="chart-axis"
          x1={defaultLayout.padding}
          x2={defaultLayout.padding}
          y1={defaultLayout.padding / 2}
          y2={defaultLayout.height - defaultLayout.padding}
        />
        <text className="chart-axis-label" x={defaultLayout.width / 2} y={defaultLayout.height - 2}>
          {view.xAxisLabel}
        </text>
        <text
          className="chart-axis-label chart-axis-label-y"
          transform={`translate(14 ${defaultLayout.height / 2}) rotate(-90)`}
        >
          distance_px
        </text>
        {view.distancePolylines.map((points, index) => (
          <polyline className="chart-distance-line" key={`distance-line-${index}`} points={points} />
        ))}
        {view.trendPolyline !== null ? (
          <polyline className="chart-trend-line" points={view.trendPolyline} />
        ) : null}
        {view.samplePoints.map((point) => (
          <circle
            className={samplePointClassName(point.sample, view.samplePointClassName)}
            cx={point.x}
            cy={point.y}
            key={`sample-${point.sample.frameIndex}-${point.sample.relativeTimeS}`}
            r="4"
          >
            <title>{sampleTooltipText(point.sample, true)}</title>
          </circle>
        ))}
        {view.invalidPoints.map((point) => (
          <circle
            className="chart-invalid-point"
            cx={point.x}
            cy={point.y}
            key={`invalid-${point.sample.frameIndex}-${point.sample.relativeTimeS}`}
            r="4"
          >
            <title>{sampleTooltipText(point.sample, false)}</title>
          </circle>
        ))}
        {view.trendPoints.map((point) => (
          <circle
            className={
              point.bin.count < lowConfidenceBinCount
                ? "chart-trend-point low-confidence"
                : "chart-trend-point"
            }
            cx={point.x}
            cy={point.y}
            key={`trend-${point.bin.temperatureCenter}`}
            r="4.5"
          >
            <title>{binTooltipText(point.bin)}</title>
          </circle>
        ))}
        {view.jumpMarkers.map((marker) => (
          <path
            className="chart-jump-marker"
            d={`M ${marker.x - 6} ${marker.y - 9} L ${marker.x + 6} ${marker.y - 9} L ${marker.x} ${marker.y - 21} Z`}
            key={`jump-${marker.sample.frameIndex}-${marker.sample.relativeTimeS}`}
          >
            <title>{`jump > ${jumpThresholdPx}px\n${sampleTooltipText(marker.sample, true)}`}</title>
          </path>
        ))}
        {view.latestPoint ? (
          <circle
            className="chart-current-point"
            cx={view.latestPoint.x}
            cy={view.latestPoint.y}
            r="7"
          >
            <title>{sampleTooltipText(view.latestPoint.sample, true)}</title>
          </circle>
        ) : null}
      </svg>
      {mode === "temperature_distance" ? (
        <p className="chart-explanation">
          原始点以散点显示，趋势线为按温度分箱后的均值/中位数；不会按采样顺序直接连接原始点。
        </p>
      ) : null}
      <div className="chart-footer">
        <span>{`${view.validCount} valid`}</span>
        <span>{`${view.invalidCount} invalid`}</span>
      </div>
    </section>
  );
}

function buildDistanceTimeView(samples: TemperatureDistanceSample[], jumpThresholdPx: number) {
  const domains = distanceTimeDomains(samples);
  const segments = buildDistanceTimeLineSegments(samples);
  const samplePoints = segments
    .flat()
    .map((point) => distanceTimeChartPoint(point, domains, defaultLayout));
  const invalidPoints = buildDistanceTimeInvalidChartPoints(samples, domains, defaultLayout);
  const distancePolylines = segments
    .filter((segment) => segment.length > 1)
    .map((segment) =>
      segment
        .map((point) => distanceTimeChartPoint(point, domains, defaultLayout))
        .map((point) => `${round(point.x)},${round(point.y)}`)
        .join(" "),
    );
  const jumpMarkers = segments.flatMap((segment) =>
    buildJumpMarkers(
      segment.map((point) => distanceTimeChartPoint(point, domains, defaultLayout)),
      jumpThresholdPx,
    ),
  );

  return {
    title: "间距-时间实时曲线",
    subtitle: "Distance vs Time",
    xAxisLabel: "Time (s)",
    samplePointClassName: "chart-sample-point",
    domains,
    distancePolylines,
    trendPolyline: null,
    samplePoints,
    invalidPoints,
    trendPoints: [],
    jumpMarkers,
    latestPoint: samplePoints.at(-1) ?? null,
    validCount: samplePoints.length,
    invalidCount: samples.length - samplePoints.length,
  };
}

function buildTemperatureDistanceView(
  samples: TemperatureDistanceSample[],
  jumpThresholdPx: number,
) {
  const scatter = buildTemperatureDistanceScatter(samples);
  const bins = buildTemperatureDistanceBins(samples);
  const domains = temperatureDistanceDomains(samples, bins);
  const samplePoints = scatter.valid.map((sample) =>
    temperatureDistanceChartPoint(sample, domains, defaultLayout),
  );
  const invalidPoints = buildTemperatureDistanceInvalidChartPoints(
    scatter.invalid,
    domains,
    defaultLayout,
  );
  const trendPoints = bins.map((bin) => trendChartPoint(bin, domains, defaultLayout));
  const trendPolyline =
    trendPoints.length > 1
      ? trendPoints.map((point) => `${round(point.x)},${round(point.y)}`).join(" ")
      : null;
  const jumpMarkers = buildJumpMarkers(samplePoints, jumpThresholdPx);

  return {
    title: "温度-间距关系",
    subtitle: "Temperature vs Distance",
    xAxisLabel: "Temperature (°C)",
    samplePointClassName: "chart-scatter-point",
    domains,
    distancePolylines: [],
    trendPolyline,
    samplePoints,
    invalidPoints,
    trendPoints,
    jumpMarkers,
    latestPoint: samplePoints.at(-1) ?? null,
    validCount: samplePoints.length,
    invalidCount: samples.length - samplePoints.length,
  };
}

function distanceTimeChartPoint(
  point: DistanceTimePoint,
  domains: ReturnType<typeof distanceTimeDomains>,
  layout: ChartLayout,
): SampleChartPoint {
  return {
    sample: point.sample,
    x: scaleX(point.xValue, domains.x, layout),
    y: scaleY(point.distancePx, domains.y, layout),
  };
}

function temperatureDistanceChartPoint(
  sample: TemperatureDistanceSample,
  domains: ReturnType<typeof temperatureDistanceDomains>,
  layout: ChartLayout,
): SampleChartPoint {
  return {
    sample,
    x: scaleX(sample.temperatureC as number, domains.x, layout),
    y: scaleY(sample.distancePx as number, domains.y, layout),
  };
}

function trendChartPoint(
  bin: TemperatureDistanceBin,
  domains: ReturnType<typeof temperatureDistanceDomains>,
  layout: ChartLayout,
): TrendChartPoint {
  return {
    bin,
    x: scaleX(bin.temperatureCenter, domains.x, layout),
    y: scaleY(bin.meanDistancePx, domains.y, layout),
  };
}

function buildDistanceTimeInvalidChartPoints(
  samples: TemperatureDistanceSample[],
  domains: ReturnType<typeof distanceTimeDomains>,
  layout: ChartLayout,
): SampleChartPoint[] {
  return buildInvalidChartPoints(
    samples.filter((sample) => !isDistanceTimePoint(sample)),
    (sample, index, denominator) =>
      Number.isFinite(distanceTimeXValue(sample))
        ? scaleXClamped(distanceTimeXValue(sample), domains.x, layout)
        : layout.padding + (plotWidth(layout) * index) / denominator,
    layout,
  );
}

function buildTemperatureDistanceInvalidChartPoints(
  samples: TemperatureDistanceSample[],
  domains: ReturnType<typeof temperatureDistanceDomains>,
  layout: ChartLayout,
): SampleChartPoint[] {
  return buildInvalidChartPoints(
    samples,
    (sample, index, denominator) =>
      sample.temperatureC === null
        ? layout.padding + (plotWidth(layout) * index) / denominator
        : scaleXClamped(sample.temperatureC, domains.x, layout),
    layout,
  );
}

function buildInvalidChartPoints(
  samples: TemperatureDistanceSample[],
  xForSample: (sample: TemperatureDistanceSample, index: number, denominator: number) => number,
  layout: ChartLayout,
): SampleChartPoint[] {
  const denominator = Math.max(1, samples.length - 1);
  return samples.map((sample, index) => ({
    sample,
    x: xForSample(sample, index, denominator),
    y: layout.height - layout.padding + 14,
  }));
}

function buildJumpMarkers(points: SampleChartPoint[], jumpThresholdPx: number): SampleChartPoint[] {
  const markers: SampleChartPoint[] = [];
  for (let index = 1; index < points.length; index += 1) {
    const previous = points[index - 1].sample.distancePx;
    const current = points[index].sample.distancePx;
    if (
      previous !== null &&
      current !== null &&
      Math.abs(current - previous) > jumpThresholdPx
    ) {
      markers.push(points[index]);
    }
  }
  return markers;
}

function samplePointClassName(sample: TemperatureDistanceSample, baseClassName: string): string {
  return sample.quality < 0.65 ? `${baseClassName} low-quality` : baseClassName;
}

function sampleTooltipText(sample: TemperatureDistanceSample, displayValid: boolean): string {
  return [
    `Frame ${sample.frameIndex}`,
    `temperature: ${sample.temperatureC === null ? "N/A" : `${sample.temperatureC.toFixed(2)} °C`}`,
    `distance: ${sample.distancePx === null ? "N/A" : `${sample.distancePx.toFixed(2)} px`}`,
    `status: ${sample.status}`,
    `quality: ${sample.quality.toFixed(2)}`,
    `time: ${formatPlaybackTime(sample.relativeTimeS)}`,
    displayValid ? "valid" : "invalid",
  ].join("\n");
}

function binTooltipText(bin: TemperatureDistanceBin): string {
  return [
    `temperature bin: ${bin.temperatureMin.toFixed(2)}-${bin.temperatureMax.toFixed(2)} °C`,
    `bin center: ${bin.temperatureCenter.toFixed(2)} °C`,
    `bin count: ${bin.count}`,
    `mean distance: ${bin.meanDistancePx.toFixed(2)} px`,
    `median distance: ${bin.medianDistancePx.toFixed(2)} px`,
    `min distance: ${bin.minDistancePx.toFixed(2)} px`,
    `max distance: ${bin.maxDistancePx.toFixed(2)} px`,
  ].join("\n");
}

function renderTicks(domain: { min: number; max: number }, axis: "x" | "y") {
  return ticksForDomain(domain).map((tick) => {
    if (axis === "x") {
      const x = scaleX(tick, domain, defaultLayout);
      return (
        <g className="chart-tick" key={`x-${tick}`}>
          <line
            x1={x}
            x2={x}
            y1={defaultLayout.padding / 2}
            y2={defaultLayout.height - defaultLayout.padding}
          />
          <text x={x} y={defaultLayout.height - 14}>
            {formatAxisValue(tick)}
          </text>
        </g>
      );
    }
    const y = scaleY(tick, domain, defaultLayout);
    return (
      <g className="chart-tick" key={`y-${tick}`}>
        <line
          x1={defaultLayout.padding}
          x2={defaultLayout.width - defaultLayout.padding / 2}
          y1={y}
          y2={y}
        />
        <text x={defaultLayout.padding - 10} y={y + 4}>
          {formatAxisValue(tick)}
        </text>
      </g>
    );
  });
}

function ticksForDomain(domain: { min: number; max: number }): number[] {
  const step = (domain.max - domain.min) / 4;
  return [0, 1, 2, 3, 4].map((index) => domain.min + step * index);
}

function formatAxisValue(value: number): string {
  return Math.abs(value) >= 100 ? value.toFixed(0) : value.toFixed(1);
}

function scaleX(value: number, domain: { min: number; max: number }, layout: ChartLayout): number {
  return layout.padding + ((value - domain.min) / (domain.max - domain.min)) * plotWidth(layout);
}

function scaleXClamped(
  value: number,
  domain: { min: number; max: number },
  layout: ChartLayout,
): number {
  return scaleX(Math.min(domain.max, Math.max(domain.min, value)), domain, layout);
}

function scaleY(value: number, domain: { min: number; max: number }, layout: ChartLayout): number {
  return (
    layout.height -
    layout.padding -
    ((value - domain.min) / (domain.max - domain.min)) * plotHeight(layout)
  );
}

function plotWidth(layout: ChartLayout): number {
  return layout.width - layout.padding * 1.5;
}

function plotHeight(layout: ChartLayout): number {
  return layout.height - layout.padding * 1.5;
}

function round(value: number): number {
  return Math.round(value * 100) / 100;
}
