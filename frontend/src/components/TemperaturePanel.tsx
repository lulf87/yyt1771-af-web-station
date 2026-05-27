import { useEffect, useState } from "react";

import {
  connectTemperatureController,
  disconnectTemperatureController,
  getCurrentTemperature,
  getTemperatureStatus,
  setTemperatureOutput,
  setTemperaturePower,
  setTemperatureTarget,
} from "../api/client";
import type { TemperatureControllerSnapshot, TemperatureReading } from "../api/types";

export function TemperaturePanel() {
  const [snapshot, setSnapshot] = useState<TemperatureControllerSnapshot | null>(null);
  const [reading, setReading] = useState<TemperatureReading | null>(null);
  const [targetValue, setTargetValue] = useState("45");
  const [powerValue, setPowerValue] = useState("0");
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void refreshStatus();
  }, []);

  async function refreshStatus() {
    await runAction("refresh", async () => {
      const [status, current] = await Promise.all([
        getTemperatureStatus(),
        getCurrentTemperature(),
      ]);
      setSnapshot(status);
      setReading(current);
      if (status.target_temperature_c !== null) {
        setTargetValue(String(status.target_temperature_c));
      }
      if (status.power_percent !== null) {
        setPowerValue(String(status.power_percent));
      }
    });
  }

  async function handleConnect() {
    await runAction("connect", async () => {
      const response = await connectTemperatureController();
      setSnapshot(response.snapshot);
      setReading(await getCurrentTemperature());
    });
  }

  async function handleDisconnect() {
    await runAction("disconnect", async () => {
      const response = await disconnectTemperatureController();
      setSnapshot(response.snapshot);
      setReading(null);
    });
  }

  async function handleTarget() {
    await runAction("target", async () => {
      const response = await setTemperatureTarget(Number(targetValue));
      setSnapshot(response.snapshot);
    });
  }

  async function handlePower() {
    await runAction("power", async () => {
      const response = await setTemperaturePower(Number(powerValue));
      setSnapshot(response.snapshot);
    });
  }

  async function handleOutput(enabled: boolean) {
    await runAction("output", async () => {
      const response = await setTemperatureOutput(enabled);
      setSnapshot(response.snapshot);
    });
  }

  async function runAction(action: string, task: () => Promise<void>) {
    setBusyAction(action);
    setError(null);
    try {
      await task();
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : "Temperature request failed.");
    } finally {
      setBusyAction(null);
    }
  }

  const busy = busyAction !== null;
  const outputEnabled = snapshot?.output_enabled === true;
  const currentTemperature = reading?.temperature_c ?? snapshot?.current_temperature_c ?? null;
  const statusText = reading?.status ?? snapshot?.status ?? "unavailable";
  const message = reading?.message ?? snapshot?.message ?? error;

  return (
    <section className="panel-section temperature-panel" aria-label="Temperature controller">
      <h2>Temperature</h2>
      <dl className="metric-list">
        <div>
          <dt>Controller</dt>
          <dd>{snapshot?.controller_type ?? "-"}</dd>
        </div>
        <div>
          <dt>Connection</dt>
          <dd>{snapshot ? (snapshot.connected ? "connected" : "disconnected") : "-"}</dd>
        </div>
        <div>
          <dt>Current</dt>
          <dd>{currentTemperature === null ? "-" : currentTemperature.toFixed(1)}</dd>
        </div>
        <div>
          <dt>Status</dt>
          <dd>{statusText}</dd>
        </div>
        {message ? (
          <div className={error ? "metric-error" : undefined}>
            <dt>Message</dt>
            <dd>{message}</dd>
          </div>
        ) : null}
      </dl>

      <div className="button-row compact temperature-actions">
        <button disabled={busy} onClick={handleConnect} type="button">
          Connect
        </button>
        <button disabled={busy} onClick={handleDisconnect} type="button">
          Disconnect
        </button>
        <button disabled={busy} onClick={refreshStatus} type="button">
          Refresh
        </button>
      </div>

      <div className="temperature-controls">
        <label>
          <span>Target C</span>
          <input
            inputMode="decimal"
            onChange={(event) => setTargetValue(event.target.value)}
            type="number"
            value={targetValue}
          />
          <button disabled={busy || !Number.isFinite(Number(targetValue))} onClick={handleTarget} type="button">
            Set
          </button>
        </label>
        <label>
          <span>Power %</span>
          <input
            inputMode="decimal"
            max="100"
            min="0"
            onChange={(event) => setPowerValue(event.target.value)}
            type="number"
            value={powerValue}
          />
          <button disabled={busy || !Number.isFinite(Number(powerValue))} onClick={handlePower} type="button">
            Set
          </button>
        </label>
      </div>

      <div className="button-row compact temperature-actions">
        <button
          className={outputEnabled ? "primary" : undefined}
          disabled={busy}
          onClick={() => handleOutput(!outputEnabled)}
          type="button"
        >
          {outputEnabled ? "Disable output" : "Enable output"}
        </button>
      </div>
    </section>
  );
}
