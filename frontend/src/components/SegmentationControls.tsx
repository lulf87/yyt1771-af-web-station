import type { BalloonEnvelopeDetectorParams, DetectorParams, SegmentationParams } from "../api/types";

interface SegmentationControlsProps {
  value: SegmentationParams;
  onChange: (value: SegmentationParams) => void;
  detector: DetectorParams;
  onDetectorChange: (value: DetectorParams) => void;
}

const numericFields: Array<{
  key: "threshold_value" | "close_kernel" | "open_kernel" | "min_component_area_px";
  label: string;
  min: number;
}> = [
  { key: "threshold_value", label: "Threshold", min: 0 },
  { key: "close_kernel", label: "Close kernel", min: 1 },
  { key: "open_kernel", label: "Open kernel", min: 1 },
  { key: "min_component_area_px", label: "Min area", min: 1 },
];

export function SegmentationControls({
  value,
  onChange,
  detector,
  onDetectorChange,
}: SegmentationControlsProps) {
  function updateNumber(key: (typeof numericFields)[number]["key"], rawValue: string) {
    const parsed = Number(rawValue);
    if (!Number.isFinite(parsed)) {
      return;
    }
    onChange({
      ...value,
      [key]: key === "threshold_value" ? Math.round(parsed) : Math.max(1, Math.round(parsed)),
    });
  }

  return (
    <div className="segmentation-controls">
      {detector.detector_kind === "balloon_envelope_detector" ? (
        <BalloonDetectorControls detector={detector} onDetectorChange={onDetectorChange} />
      ) : null}
      <label className="inline-check">
        <input
          checked={value.fill_internal_holes ?? false}
          onChange={(event) =>
            onChange({
              ...value,
              fill_internal_holes: event.currentTarget.checked,
            })
          }
          type="checkbox"
        />
        <span>Fill holes</span>
      </label>
      <label className="stacked-field">
        <span>Polarity</span>
        <select
          onChange={(event) =>
            onChange({
              ...value,
              polarity: event.currentTarget.value as SegmentationParams["polarity"],
            })
          }
          value={value.polarity}
        >
          <option value="auto">auto</option>
          <option value="dark_on_light">dark_on_light</option>
          <option value="light_on_dark">light_on_dark</option>
        </select>
      </label>
      <label className="stacked-field">
        <span>Threshold mode</span>
        <select
          onChange={(event) =>
            onChange({
              ...value,
              threshold_mode: event.currentTarget.value as SegmentationParams["threshold_mode"],
              threshold_value:
                event.currentTarget.value === "fixed" ? (value.threshold_value ?? 128) : null,
            })
          }
          value={value.threshold_mode}
        >
          <option value="otsu">otsu</option>
          <option value="adaptive">adaptive</option>
          <option value="fixed">fixed</option>
        </select>
      </label>
      <div className="two-column-fields">
        {numericFields.map((field) => (
          <label className="stacked-field" key={field.key}>
            <span>{field.label}</span>
            <input
              disabled={field.key === "threshold_value" && value.threshold_mode !== "fixed"}
              max={field.key === "threshold_value" ? 255 : undefined}
              min={field.min}
              onChange={(event) => updateNumber(field.key, event.currentTarget.value)}
              type="number"
              value={value[field.key] ?? ""}
            />
          </label>
        ))}
      </div>
    </div>
  );
}

function BalloonDetectorControls({
  detector,
  onDetectorChange,
}: {
  detector: BalloonEnvelopeDetectorParams;
  onDetectorChange: (value: DetectorParams) => void;
}) {
  return (
    <>
      <label className="stacked-field">
        <span>Envelope mode</span>
        <select
          onChange={(event) =>
            onDetectorChange({
              ...detector,
              envelope_mode: event.currentTarget.value as BalloonEnvelopeDetectorParams["envelope_mode"],
              contact_source:
                event.currentTarget.value === "open_mesh" &&
                detector.contact_source === "filled_envelope"
                  ? "bridged_foreground"
                  : detector.contact_source,
            })
          }
          value={detector.envelope_mode}
        >
          <option value="solid_balloon">solid_balloon</option>
          <option value="open_mesh">open_mesh</option>
        </select>
      </label>
      <label className="stacked-field">
        <span>Contact source</span>
        <select
          onChange={(event) =>
            onDetectorChange({
              ...detector,
              contact_source: event.currentTarget.value as BalloonEnvelopeDetectorParams["contact_source"],
            })
          }
          value={detector.contact_source}
        >
          <option value="raw_foreground">raw_foreground</option>
          <option value="bridged_foreground">bridged_foreground</option>
          <option disabled={detector.envelope_mode === "open_mesh"} value="filled_envelope">
            {detector.envelope_mode === "open_mesh"
              ? "filled_envelope (debug-only)"
              : "filled_envelope"}
          </option>
        </select>
      </label>
    </>
  );
}
