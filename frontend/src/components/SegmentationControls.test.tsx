import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import type { SegmentationParams } from "../api/types";
import { SegmentationControls } from "./SegmentationControls";

const segmentation: SegmentationParams = {
  polarity: "auto",
  threshold_mode: "otsu",
  threshold_value: null,
  blur_kernel: 3,
  close_kernel: 11,
  open_kernel: 3,
  min_component_area_px: 500,
  fill_internal_holes: true,
};

describe("SegmentationControls", () => {
  it("renders fill holes and morphology controls", () => {
    const markup = renderToStaticMarkup(
      <SegmentationControls value={segmentation} onChange={() => undefined} />,
    );

    expect(markup).toContain("Fill holes");
    expect(markup).toContain("Polarity");
    expect(markup).toContain("Close kernel");
    expect(markup).toContain("Open kernel");
    expect(markup).toContain("Min area");
  });
});
