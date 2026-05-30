import type { OfflineDataset } from "../api/types";

interface OfflineDatasetSelectorProps {
  datasets: OfflineDataset[];
  value: string;
  onChange: (datasetId: string) => void;
  disabled?: boolean;
  label?: string;
}

const ENV_DEFAULT_LABEL = "Default (YYT1771_AF_OFFLINE_DIR)";

export function OfflineDatasetSelector({
  datasets,
  value,
  onChange,
  disabled = false,
  label = "Simulation material",
}: OfflineDatasetSelectorProps) {
  return (
    <label className="stacked-field">
      <span>{label}</span>
      <select
        aria-label="Simulation material dataset"
        disabled={disabled}
        onChange={(event) => onChange(event.currentTarget.value)}
        value={value}
      >
        <option value="">{ENV_DEFAULT_LABEL}</option>
        {datasets.map((dataset) => (
          <option
            disabled={!dataset.available}
            key={dataset.dataset_id}
            value={dataset.dataset_id}
          >
            {dataset.label}
            {dataset.available ? "" : " (missing)"}
          </option>
        ))}
      </select>
    </label>
  );
}
