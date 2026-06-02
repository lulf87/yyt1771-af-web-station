import type {
  CameraOpenResponse,
  CameraStatus,
  AnalysisResponse,
  ExportFormat,
  FramePreviewMetadata,
  FreezeResponse,
  OfflineDataset,
  OfflinePlaybackFrame,
  OfflinePlaybackOpenRequest,
  OfflinePlaybackStatus,
  OfflineRunCloseResponse,
  OfflineRunFrame,
  OfflineRunErrorResponse,
  OfflineRunOpenRequest,
  OfflineRunOpenResponse,
  OfflineRunPointProbeRequest,
  OfflineRunStatus,
  OfflineRunTraceResponse,
  PointProbeResponse,
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
  SetupPointProbeRequest,
  WireAutoTuneRequest,
  WireAutoTuneResponse,
  TemperatureCommandResponse,
  TemperatureControllerSnapshot,
  TemperatureReading,
} from "./types";

export class ApiRequestError extends Error {
  readonly errorCode: string | null;
  readonly status: number | null;
  readonly sessionId: string | null;
  readonly frameIndex: number | null;
  readonly frameName: string | null;
  readonly state: string | null;

  constructor(
    message: string,
    {
      errorCode = null,
      status = null,
      sessionId = null,
      frameIndex = null,
      frameName = null,
      state = null,
    }: {
      errorCode?: string | null;
      status?: number | null;
      sessionId?: string | null;
      frameIndex?: number | null;
      frameName?: string | null;
      state?: string | null;
    } = {},
  ) {
    super(message);
    this.name = "ApiRequestError";
    this.errorCode = errorCode;
    this.status = status;
    this.sessionId = sessionId;
    this.frameIndex = frameIndex;
    this.frameName = frameName;
    this.state = state;
  }
}

export async function openCamera(
  profile = "dev_mock",
  datasetId: string | null = null,
): Promise<CameraOpenResponse> {
  return requestJson<CameraOpenResponse>("/api/camera/open", {
    method: "POST",
    body: JSON.stringify({ profile, dataset_id: datasetId }),
  });
}

export async function listOfflineDatasets(): Promise<OfflineDataset[]> {
  return requestJson<OfflineDataset[]>("/api/offline-run/datasets");
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

export async function probeSetupPoint(
  request: SetupPointProbeRequest,
): Promise<PointProbeResponse> {
  return requestJson<PointProbeResponse>("/api/setup/probe-point", {
    method: "POST",
    body: JSON.stringify(request),
  });
}

export async function wireAutoTune(
  request: WireAutoTuneRequest,
): Promise<WireAutoTuneResponse> {
  return requestJson<WireAutoTuneResponse>("/api/setup/wire-auto-tune", {
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

export async function openOfflineRun(
  request: OfflineRunOpenRequest,
): Promise<OfflineRunOpenResponse> {
  return requestJson<OfflineRunOpenResponse>("/api/offline-run/open", {
    method: "POST",
    body: JSON.stringify(request),
  });
}

export async function getOfflineRunStatus(sessionId: string): Promise<OfflineRunStatus> {
  return requestJson<OfflineRunStatus>(`/api/offline-run/${sessionId}/status`);
}

export async function nextOfflineRun(
  sessionId: string,
  signal?: AbortSignal,
): Promise<OfflineRunFrame> {
  return requestJson<OfflineRunFrame>(`/api/offline-run/${sessionId}/next`, {
    method: "POST",
    signal,
  });
}

export async function inspectOfflineRun(sessionId: string): Promise<OfflineRunFrame> {
  return requestJson<OfflineRunFrame>(`/api/offline-run/${sessionId}/inspect`, {
    method: "POST",
  });
}

export async function previousOfflineRun(sessionId: string): Promise<OfflineRunFrame> {
  return requestJson<OfflineRunFrame>(`/api/offline-run/${sessionId}/previous`, {
    method: "POST",
  });
}

export async function seekOfflineRun(
  sessionId: string,
  frameIndex: number,
): Promise<OfflineRunFrame> {
  return requestJson<OfflineRunFrame>(`/api/offline-run/${sessionId}/seek`, {
    method: "POST",
    body: JSON.stringify({ frame_index: frameIndex }),
  });
}

export async function probeOfflineRunPoint(
  sessionId: string,
  request: OfflineRunPointProbeRequest,
): Promise<PointProbeResponse> {
  return requestJson<PointProbeResponse>(`/api/offline-run/${sessionId}/probe-point`, {
    method: "POST",
    body: JSON.stringify(request),
  });
}

export async function closeOfflineRun(sessionId: string): Promise<OfflineRunCloseResponse> {
  return requestJson<OfflineRunCloseResponse>(`/api/offline-run/${sessionId}/close`, {
    method: "POST",
  });
}

export async function getOfflineRunTrace(sessionId: string): Promise<OfflineRunTraceResponse> {
  return requestJson<OfflineRunTraceResponse>(`/api/offline-run/${sessionId}/trace`);
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
  let response: Response;
  try {
    response = await fetch(path, {
      headers: {
        "Content-Type": "application/json",
        ...(init?.headers ?? {}),
      },
      ...init,
    });
  } catch (caughtError) {
    if (caughtError instanceof DOMException && caughtError.name === "AbortError") {
      throw caughtError;
    }
    throw new ApiRequestError(
      caughtError instanceof Error ? caughtError.message : "Network request failed.",
      {
        errorCode: "network_error",
      },
    );
  }
  if (!response.ok) {
    const detail = await response.text();
    const structured = parseOfflineRunError(detail);
    if (structured !== null) {
      throw new ApiRequestError(structured.message, {
        errorCode: structured.error_code,
        status: response.status,
        sessionId: structured.session_id ?? null,
        frameIndex: structured.frame_index ?? null,
        frameName: structured.frame_name ?? null,
        state: structured.state,
      });
    }
    throw new ApiRequestError(detail || `Request failed with status ${response.status}`, {
      status: response.status,
    });
  }
  return (await response.json()) as T;
}

function parseOfflineRunError(payload: string): OfflineRunErrorResponse | null {
  try {
    const parsed = JSON.parse(payload) as Partial<OfflineRunErrorResponse>;
    if (typeof parsed.error_code === "string" && typeof parsed.message === "string") {
      return {
        error_code: parsed.error_code,
        message: parsed.message,
        state: parsed.state === "error" ? "error" : "error",
        session_id: parsed.session_id ?? null,
        frame_index: parsed.frame_index ?? null,
        frame_name: parsed.frame_name ?? null,
      };
    }
  } catch {
    return null;
  }
  return null;
}

function filenameFromDisposition(value: string | null): string | null {
  if (value === null) {
    return null;
  }
  const match = /filename="?([^";]+)"?/i.exec(value);
  return match ? match[1] : null;
}
