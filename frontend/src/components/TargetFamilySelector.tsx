import type { TargetFamily } from "../api/types";

interface TargetFamilySelectorProps {
  value: TargetFamily;
  onChange: (targetFamily: TargetFamily) => void;
}

const targetFamilies: Array<{ label: string; value: TargetFamily }> = [
  { label: "Balloon envelope", value: "balloon_envelope" },
  { label: "Wire strip", value: "wire_strip" },
];

export function TargetFamilySelector({ value, onChange }: TargetFamilySelectorProps) {
  return (
    <div className="segmented-control" role="group" aria-label="Target family">
      {targetFamilies.map((target) => (
        <button
          aria-pressed={value === target.value}
          className={value === target.value ? "segment active" : "segment"}
          key={target.value}
          onClick={() => onChange(target.value)}
          type="button"
        >
          {target.label}
        </button>
      ))}
    </div>
  );
}
