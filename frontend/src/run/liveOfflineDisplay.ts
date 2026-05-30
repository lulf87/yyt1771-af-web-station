export function formatPlaybackTime(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined || !Number.isFinite(seconds)) {
    return "N/A";
  }
  const clamped = Math.max(0, seconds);
  const minutes = Math.floor(clamped / 60);
  const remainder = clamped - minutes * 60;
  if (minutes > 0) {
    return `${minutes}:${remainder.toFixed(1).padStart(4, "0")}`;
  }
  return `${remainder.toFixed(1)}s`;
}

export function runtimeNumber(
  runtime: Record<string, unknown> | undefined,
  key: string,
): number | null {
  if (runtime === undefined) {
    return null;
  }
  const value = runtime[key];
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

export function runtimeString(
  runtime: Record<string, unknown> | undefined,
  key: string,
): string | null {
  if (runtime === undefined) {
    return null;
  }
  const value = runtime[key];
  return typeof value === "string" && value.trim() !== "" ? value : null;
}
