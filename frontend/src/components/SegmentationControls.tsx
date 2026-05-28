import type { SegmentationParams } from "../api/types";

interface SegmentationControlsProps {
  value: SegmentationParams;
  onChange: (value: SegmentationParams) => void;
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

export function SegmentationControls({ value, onChange }: SegmentationControlsProps) {
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
