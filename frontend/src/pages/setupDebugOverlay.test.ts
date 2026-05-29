import { describe, expect, it } from "vitest";

import { debugOverlayUrlWithLayers } from "./setupDebugOverlay";

describe("setup debug overlay URL", () => {
  it("adds layer toggles to the backend debug overlay URL", () => {
    const url = debugOverlayUrlWithLayers("/api/setup/debug-overlay/dbg_1.png?max_width=1200", {
      showRawForeground: true,
      showMorphologyForeground: false,
      showFilledEnvelope: true,
      showSelectedContour: true,
      showRejectedCandidates: false,
    });

    expect(url).toContain("show_raw_foreground=true");
    expect(url).toContain("show_morphology_foreground=false");
    expect(url).toContain("show_filled_envelope=true");
    expect(url).toContain("show_selected_contour=true");
    expect(url).toContain("show_rejected_candidates=false");
  });
});
