import type { RotatedRoi } from "../api/types";

interface RoiEditorProps {
  roi: RotatedRoi;
  onChange: (roi: RotatedRoi) => void;
}

const roiFields: Array<{ key: keyof Omit<RotatedRoi, "coordinate_space">; label: string; min?: number }> = [
  { key: "center_x", label: "Center X" },
  { key: "center_y", label: "Center Y" },
  { key: "width", label: "Width", min: 1 },
  { key: "height", label: "Height", min: 1 },
  { key: "angle_deg", label: "Angle" },
];

export function RoiEditor({ roi, onChange }: RoiEditorProps) {
  function updateField(key: keyof Omit<RotatedRoi, "coordinate_space">, value: string) {
    const nextValue = Number(value);
    if (!Number.isFinite(nextValue)) {
      return;
    }
    onChange({
      ...roi,
      [key]: nextValue,
      coordinate_space: "acquisition",
    });
  }

  return (
    <div className="roi-editor">
      {roiFields.map((field) => (
        <label key={field.key}>
          <span>{field.label}</span>
          <input
            min={field.min}
            onChange={(event) => updateField(field.key, event.currentTarget.value)}
            step="1"
            type="number"
            value={roi[field.key]}
          />
        </label>
      ))}
    </div>
  );
}
