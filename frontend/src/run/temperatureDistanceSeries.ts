import type { DetectionStatus, OfflineRunFrame } from "../api/types";
import { runtimeNumber } from "./liveOfflineDisplay";

export interface TemperatureDistanceSample {
  frameIndex: number;
  relativeTimeS: number;
  temperatureC: number | null;
  distancePx: number | null;
  status: DetectionStatus;
  quality: number;
  valid: boolean;
}

export interface ChartDomain {
  min: number;
  max: number;
}

export interface TemperatureDistanceDomains {
  x: ChartDomain;
  y: ChartDomain;
}

export interface DistanceTimePoint {
  sample: TemperatureDistanceSample;
  xValue: number;
  distancePx: number;
}

export interface TemperatureDistanceScatter {
  valid: TemperatureDistanceSample[];
  invalid: TemperatureDistanceSample[];
}

export interface TemperatureDistanceBin {
  temperatureCenter: number;
  temperatureMin: number;
  temperatureMax: number;
  count: number;
  meanDistancePx: number;
  medianDistancePx: number;
  minDistancePx: number;
  maxDistancePx: number;
  stdDistancePx: number;
}

interface TemperatureDistanceBinOptions {
  binSizeC?: number;
}

const MIN_DOMAIN_SPAN = 1;
const MIN_DISTANCE_TIME_Y_DOMAIN_SPAN = 10;
const DOMAIN_MARGIN_RATIO = 0.08;
const DEFAULT_TEMPERATURE_BIN_SIZE_C = 0.1;

export function sampleFromOfflineRunFrame(frame: OfflineRunFrame): TemperatureDistanceSample {
  const temperatureC = runtimeNumber(frame.runtime, "temperature_c");
  const distancePx = finiteOrNull(frame.detection.distance_px);
  const valid =
    frame.detection.valid === true &&
    frame.detection.status === "ok" &&
    distancePx !== null;

  return {
    frameIndex: frame.frame_index,
    relativeTimeS: frame.relative_time_s,
    temperatureC,
    distancePx,
    status: frame.detection.status,
    quality: frame.detection.quality,
    valid,
  };
}

export function appendLiveTemperatureDistanceSample(
  samples: TemperatureDistanceSample[],
  frame: OfflineRunFrame,
  {
    fromPlaybackLoop,
    maxSamples = 2000,
  }: {
    fromPlaybackLoop: boolean;
    maxSamples?: number;
  },
): TemperatureDistanceSample[] {
  if (!fromPlaybackLoop) {
    return samples;
  }
  return [...samples, sampleFromOfflineRunFrame(frame)].slice(-maxSamples);
}

export function buildValidLineSegments(
  samples: TemperatureDistanceSample[],
): TemperatureDistanceSample[][] {
  const segments: TemperatureDistanceSample[][] = [];
  let current: TemperatureDistanceSample[] = [];

  for (const sample of samples) {
    if (isNormalTemperatureDistancePoint(sample)) {
      current.push(sample);
      continue;
    }
    if (current.length > 0) {
      segments.push(current);
      current = [];
    }
  }
  if (current.length > 0) {
    segments.push(current);
  }
  return segments;
}

export function buildDistanceTimeLineSegments(
  samples: TemperatureDistanceSample[],
): DistanceTimePoint[][] {
  const segments: DistanceTimePoint[][] = [];
  let current: DistanceTimePoint[] = [];

  for (const sample of samples) {
    if (isDistanceTimePoint(sample)) {
      current.push({
        sample,
        xValue: distanceTimeXValue(sample),
        distancePx: sample.distancePx as number,
      });
      continue;
    }
    if (current.length > 0) {
      segments.push(current);
      current = [];
    }
  }
  if (current.length > 0) {
    segments.push(current);
  }
  return segments;
}

export function buildTemperatureDistanceScatter(
  samples: TemperatureDistanceSample[],
): TemperatureDistanceScatter {
  return {
    valid: samples.filter(isNormalTemperatureDistancePoint),
    invalid: samples.filter((sample) => !isNormalTemperatureDistancePoint(sample)),
  };
}

export function buildTemperatureDistanceBins(
  samples: TemperatureDistanceSample[],
  { binSizeC = DEFAULT_TEMPERATURE_BIN_SIZE_C }: TemperatureDistanceBinOptions = {},
): TemperatureDistanceBin[] {
  const safeBinSizeC = binSizeC > 0 && Number.isFinite(binSizeC) ? binSizeC : DEFAULT_TEMPERATURE_BIN_SIZE_C;
  const grouped = new Map<
    number,
    {
      temperatureMin: number;
      temperatureMax: number;
      distances: number[];
    }
  >();

  for (const sample of buildTemperatureDistanceScatter(samples).valid) {
    const temperature = sample.temperatureC as number;
    const distance = sample.distancePx as number;
    const binIndex = Math.floor(temperature / safeBinSizeC);
    const temperatureMin = normalizeNumber(binIndex * safeBinSizeC);
    const temperatureMax = normalizeNumber(temperatureMin + safeBinSizeC);
    const group = grouped.get(binIndex);
    if (group === undefined) {
      grouped.set(binIndex, {
        temperatureMin,
        temperatureMax,
        distances: [distance],
      });
    } else {
      group.distances.push(distance);
    }
  }

  return Array.from(grouped.entries())
    .sort(([leftIndex], [rightIndex]) => leftIndex - rightIndex)
    .map(([, group]) => {
      const sortedDistances = [...group.distances].sort((left, right) => left - right);
      const count = sortedDistances.length;
      const meanDistancePx = mean(sortedDistances);
      return {
        temperatureCenter: normalizeNumber((group.temperatureMin + group.temperatureMax) / 2),
        temperatureMin: group.temperatureMin,
        temperatureMax: group.temperatureMax,
        count,
        meanDistancePx,
        medianDistancePx: median(sortedDistances),
        minDistancePx: sortedDistances[0],
        maxDistancePx: sortedDistances[count - 1],
        stdDistancePx: standardDeviation(sortedDistances, meanDistancePx),
      };
    });
}

export function isDistanceTimePoint(sample: TemperatureDistanceSample): boolean {
  return sample.valid && sample.distancePx !== null && Number.isFinite(distanceTimeXValue(sample));
}

export function isNormalTemperatureDistancePoint(sample: TemperatureDistanceSample): boolean {
  return sample.valid && sample.temperatureC !== null && sample.distancePx !== null;
}

export function distanceTimeDomains(samples: TemperatureDistanceSample[]): TemperatureDistanceDomains {
  const points = buildDistanceTimeLineSegments(samples).flat();
  const x = paddedDomain(points.map((point) => point.xValue));
  return {
    x: {
      min: Math.max(0, x.min),
      max: Math.max(x.max, Math.max(0, x.min) + MIN_DOMAIN_SPAN),
    },
    y: paddedDomain(
      points.map((point) => point.distancePx),
      MIN_DISTANCE_TIME_Y_DOMAIN_SPAN,
    ),
  };
}

export function temperatureDistanceDomains(
  samples: TemperatureDistanceSample[],
  bins: TemperatureDistanceBin[] = buildTemperatureDistanceBins(samples),
): TemperatureDistanceDomains {
  const validSamples = buildTemperatureDistanceScatter(samples).valid;
  return {
    x: paddedDomain([
      ...validSamples.map((sample) => sample.temperatureC as number),
      ...bins.flatMap((bin) => [bin.temperatureMin, bin.temperatureCenter, bin.temperatureMax]),
    ]),
    y: paddedDomain([
      ...validSamples.map((sample) => sample.distancePx as number),
      ...bins.flatMap((bin) => [
        bin.meanDistancePx,
        bin.medianDistancePx,
        bin.minDistancePx,
        bin.maxDistancePx,
      ]),
    ]),
  };
}

export function distanceTimeXValue(sample: TemperatureDistanceSample): number {
  return Number.isFinite(sample.relativeTimeS) ? sample.relativeTimeS : sample.frameIndex;
}

function paddedDomain(values: number[], minimumSpan = MIN_DOMAIN_SPAN): ChartDomain {
  if (values.length === 0) {
    return { min: 0, max: minimumSpan };
  }

  const minValue = Math.min(...values);
  const maxValue = Math.max(...values);
  const center = (minValue + maxValue) / 2;
  const span = Math.max(maxValue - minValue, minimumSpan);
  const paddedSpan = span * (1 + DOMAIN_MARGIN_RATIO * 2);
  return {
    min: center - paddedSpan / 2,
    max: center + paddedSpan / 2,
  };
}

function finiteOrNull(value: number | null | undefined): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function mean(values: number[]): number {
  return values.reduce((total, value) => total + value, 0) / values.length;
}

function median(sortedValues: number[]): number {
  const middleIndex = Math.floor(sortedValues.length / 2);
  if (sortedValues.length % 2 === 1) {
    return sortedValues[middleIndex];
  }
  return (sortedValues[middleIndex - 1] + sortedValues[middleIndex]) / 2;
}

function standardDeviation(values: number[], average: number): number {
  const variance =
    values.reduce((total, value) => total + (value - average) ** 2, 0) / values.length;
  return Math.sqrt(variance);
}

function normalizeNumber(value: number): number {
  return Number(value.toFixed(12));
}
