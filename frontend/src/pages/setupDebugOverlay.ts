export interface DebugOverlayLayers {
  showRawForeground: boolean;
  showMorphologyForeground: boolean;
  showFilledEnvelope: boolean;
  showSelectedContour: boolean;
  showRejectedCandidates: boolean;
}

export function debugOverlayUrlWithLayers(
  baseUrl: string | null | undefined,
  layers: DebugOverlayLayers,
): string | null {
  if (!baseUrl) {
    return null;
  }
  const separator = baseUrl.includes("?") ? "&" : "?";
  const params = new URLSearchParams({
    show_raw_foreground: String(layers.showRawForeground),
    show_morphology_foreground: String(layers.showMorphologyForeground),
    show_filled_envelope: String(layers.showFilledEnvelope),
    show_selected_contour: String(layers.showSelectedContour),
    show_rejected_candidates: String(layers.showRejectedCandidates),
  });
  return `${baseUrl}${separator}${params.toString()}`;
}
