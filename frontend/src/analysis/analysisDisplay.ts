import type { AnalysisResponse } from "../api/types";

export interface AnalysisSummaryRow {
  label: string;
  value: string;
}

export function af95Label(analysis: AnalysisResponse | null): string {
  const value = analysis?.result?.af95_temperature_c;
  return value === undefined || value === null ? "-" : `${value.toFixed(1)} C`;
}

export function analysisSummaryRows(analysis: AnalysisResponse | null): AnalysisSummaryRow[] {
  if (analysis === null) {
    return [
      { label: "Status", value: "waiting" },
      { label: "Af-95", value: "-" },
      { label: "Invalid samples", value: "-" },
    ];
  }

  return [
    { label: "Status", value: analysis.status },
    { label: "Method", value: analysis.method },
    { label: "Af-95", value: af95Label(analysis) },
    {
      label: "Invalid samples",
      value: analysis.result ? String(analysis.result.invalid_sample_count) : "-",
    },
    {
      label: "Valid samples",
      value: analysis.result ? String(analysis.result.valid_sample_count) : "-",
    },
  ];
}
