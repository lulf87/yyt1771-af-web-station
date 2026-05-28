import type {
  CameraOpenResponse,
  CameraStatus,
  AnalysisResponse,
  ExportFormat,
  FramePreviewMetadata,
  FreezeResponse,
  OfflinePlaybackFrame,
  OfflinePlaybackOpenRequest,
  OfflinePlaybackStatus,
  RunListResponse,
  RunSamplesResponse,
  RunStartRequest,
  RunStartResponse,
  RunStatusResponse,
  RunStopResponse,
  SetupConfirmRequest,
  SetupConfirmResponse,
  SetupDetectRequest,
  SetupDetectResponse,
  TemperatureCommandResponse,
  TemperatureControllerSnapshot,
  TemperatureReading,
} from "./types";

export async function openCamera(profile = "dev_mock"): Promise<CameraOpenResponse> {
  return requestJson<CameraOpenResponse>("/api/camera/open", {
    method: "POST",
    body: JSON.stringify({ profile }),
  });
}

export async function getCameraStatus(): Promise<CameraStatus> {
  return requestJson<CameraStatus>("/api/camera/status");
}

export async function getLatestFramePreview(maxWidth = 1200): Promise<FramePreviewMetadata> {
  return requestJson<FramePreviewMetadata>(`/api/camera/frame/latest?max_width=${maxWidth}`);
}

export async function freezeSetupFrame(): Promise<FreezeResponse> {
  return requestJson<FreezeResponse>("/api/setup/freeze", {
    method: "POST",
    body: JSON.stringify({ source: "latest" }),
  });
}

export async function detectSetupFrame(
  request: SetupDetectRequest,
): Promise<SetupDetectResponse> {
  return requestJson<SetupDetectResponse>("/api/setup/detect", {
    method: "POST",
    body: JSON.stringify(request),
  });
}

export async function confirmSetup(
  request: SetupConfirmRequest,
): Promise<SetupConfirmResponse> {
  return requestJson<SetupConfirmResponse>("/api/setup/confirm", {
    method: "POST",
    body: JSON.stringify(request),
  });
}

export async function startRun(request: RunStartRequest): Promise<RunStartResponse> {
  return requestJson<RunStartResponse>("/api/runs/start", {
    method: "POST",
    body: JSON.stringify(request),
  });
}

export async function getRunStatus(runId: string): Promise<RunStatusResponse> {
  return requestJson<RunStatusResponse>(`/api/runs/${runId}/status`);
}

export async function stopRun(runId: string): Promise<RunStopResponse> {
  return requestJson<RunStopResponse>(`/api/runs/${runId}/stop`, {
    method: "POST",
  });
}

export async function getRunSamples(runId: string): Promise<RunSamplesResponse> {
  return requestJson<RunSamplesResponse>(`/api/runs/${runId}/samples`);
}

export async function openOfflinePlayback(
  request: OfflinePlaybackOpenRequest,
): Promise<OfflinePlaybackStatus> {
  return requestJson<OfflinePlaybackStatus>("/api/offline-playback/open", {
    method: "POST",
    body: JSON.stringify(request),
  });
}

export async function getOfflinePlaybackStatus(): Promise<OfflinePlaybackStatus> {
  return requestJson<OfflinePlaybackStatus>("/api/offline-playback/status");
}

export async function seekOfflinePlayback(frameIndex: number): Promise<OfflinePlaybackFrame> {
  return requestJson<OfflinePlaybackFrame>("/api/offline-playback/seek", {
    method: "POST",
    body: JSON.stringify({ frame_index: frameIndex }),
  });
}

export async function nextOfflinePlayback(failuresOnly: boolean): Promise<OfflinePlaybackFrame> {
  return requestJson<OfflinePlaybackFrame>("/api/offline-playback/next", {
    method: "POST",
    body: JSON.stringify({ failures_only: failuresOnly }),
  });
}

export async function previousOfflinePlayback(
  failuresOnly: boolean,
): Promise<OfflinePlaybackFrame> {
  return requestJson<OfflinePlaybackFrame>("/api/offline-playback/previous", {
    method: "POST",
    body: JSON.stringify({ failures_only: failuresOnly }),
  });
}

export async function listRuns(): Promise<RunListResponse> {
  return requestJson<RunListResponse>("/api/runs");
}

export async function postRunAnalysis(runId: string): Promise<AnalysisResponse> {
  return requestJson<AnalysisResponse>(`/api/runs/${runId}/analysis`, {
    method: "POST",
  });
}

export async function getRunAnalysis(runId: string): Promise<AnalysisResponse> {
  return requestJson<AnalysisResponse>(`/api/runs/${runId}/analysis`);
}

export async function downloadRunExport(runId: string, format: ExportFormat): Promise<void> {
  const response = await fetch(`/api/runs/${encodeURIComponent(runId)}/export.${format}`);
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Export failed with status ${response.status}`);
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filenameFromDisposition(response.headers.get("Content-Disposition")) ?? "";
  document.body.append(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

export async function getTemperatureStatus(): Promise<TemperatureControllerSnapshot> {
  return requestJson<TemperatureControllerSnapshot>("/api/temperature/status");
}

export async function connectTemperatureController(): Promise<TemperatureCommandResponse> {
  return requestJson<TemperatureCommandResponse>("/api/temperature/connect", {
    method: "POST",
  });
}

export async function disconnectTemperatureController(): Promise<TemperatureCommandResponse> {
  return requestJson<TemperatureCommandResponse>("/api/temperature/disconnect", {
    method: "POST",
  });
}

export async function getCurrentTemperature(): Promise<TemperatureReading> {
  return requestJson<TemperatureReading>("/api/temperature/current");
}

export async function setTemperatureTarget(
  target_c: number,
): Promise<TemperatureCommandResponse> {
  return requestJson<TemperatureCommandResponse>("/api/temperature/target", {
    method: "POST",
    body: JSON.stringify({ target_c }),
  });
}

export async function setTemperaturePower(
  power_percent: number,
): Promise<TemperatureCommandResponse> {
  return requestJson<TemperatureCommandResponse>("/api/temperature/power", {
    method: "POST",
    body: JSON.stringify({ power_percent }),
  });
}

export async function setTemperatureOutput(
  enabled: boolean,
): Promise<TemperatureCommandResponse> {
  return requestJson<TemperatureCommandResponse>("/api/temperature/output", {
    method: "POST",
    body: JSON.stringify({ enabled }),
  });
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    ...init,
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Request failed with status ${response.status}`);
  }
  return (await response.json()) as T;
}

function filenameFromDisposition(value: string | null): string | null {
  if (value === null) {
    return null;
  }
  const match = /filename="?([^";]+)"?/i.exec(value);
  return match ? match[1] : null;
}
