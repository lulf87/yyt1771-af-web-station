import type { RunSample } from "../api/types";

export interface SampleRow {
  index: number;
  status: string;
  distance: string;
  temperature: string;
  temperatureStatus: string;
  quality: string;
}

export function sampleRows(samples: RunSample[]): SampleRow[] {
  return samples.map((sample) => ({
    index: sample.sample_index,
    status: sample.detection.status,
    distance:
      sample.detection.distance_px === null ? "-" : sample.detection.distance_px.toFixed(2),
    temperature: sample.temperature_c === null ? "-" : sample.temperature_c.toFixed(1),
    temperatureStatus: sample.temperature_status,
    quality: sample.detection.quality.toFixed(2),
  }));
}

export function latestSample(samples: RunSample[]): RunSample | null {
  return samples.length > 0 ? samples[samples.length - 1] : null;
}
