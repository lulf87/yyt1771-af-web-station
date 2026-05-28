# Detection Debug Diagnostics and Mesh Envelope Notes

This phase adds diagnostic visibility for the current NumPy detector path. It does not implement a Hik MVS adapter, does not add OpenCV, does not add a third public detector, and does not change the formal A/B point contract.

## Why This Exists

Real offline balloon captures can contain an open mesh or stent-like structure rather than a closed solid envelope. Inside the ROI there may be bright background holes, dark metal strands, shadows, fixtures, and regions that connect to the ROI crop boundary.

When detection fails with `caliper_contact_on_roi_boundary`, the important question is not only whether the visible object appears close to the ROI edge. We must also inspect what the detector actually selected as foreground, which connected component it chose, and which contour produced the candidate contacts.

## Current Balloon Detector Behavior

`BalloonEnvelopeDetector` is still a NumPy MVP:

- build an acquisition-coordinate ROI mask
- threshold ROI pixels
- choose dark/light polarity
- apply close/open morphology
- optionally fill internal holes
- select connected components
- choose contour support points along the ROI measurement direction
- reject contacts too close to the ROI boundary

This is not yet a dedicated mesh-envelope reconstruction algorithm.

## Why Open Meshes Are Harder Than Closed Balloons

For a closed, dark object on a light background, thresholding often produces one clean connected component. For an open mesh:

- holes can make the ROI center land on bright background
- dark strands may be disconnected or weakly bridged
- shadows and fixtures can join into a larger foreground component
- the largest connected component may be background-like rather than the intended envelope
- filling holes can enlarge an already-wrong component

Because `polarity: auto` can use the preferred ROI center point, a center point in a bright hole may select light foreground. A center point on a dark strand or shadow may select dark foreground. The debug diagnostics record this decision.

## Why Boundary Rejection Is Still Correct

`caliper_contact_on_roi_boundary` protects the measurement contract. If the selected contour touches the ROI boundary in the measurement direction, the candidate contact may be created by ROI cropping rather than by a true target contour.

Do not disable `reject_contact_on_roi_boundary` to make A/B points appear. Instead, inspect the debug mask:

- foreground mask: what thresholding selected
- selected component: which connected component was measured
- selected contour: which contour supplied contact candidates
- rejected candidates: where the detector would have placed support contacts before rejection
- boundary margin lines: why the candidate was rejected

Invalid detections still keep formal `point_a`, `point_b`, and `distance_px` as `null`. Rejected candidate points are debug-only evidence.

## Setup Page Debug Controls

The Setup page includes segmentation controls that affect only the current setup detection and the confirmed local measurement definition:

- `polarity`: `auto`, `dark_on_light`, `light_on_dark`
- `threshold_mode`: `otsu`, `adaptive`, `fixed`
- `threshold_value`: enabled for fixed threshold
- `close_kernel`
- `open_kernel`
- `min_component_area_px`

Use these controls to test whether the failure is caused by polarity selection, thresholding, component size filtering, or ROI crop contact.

## Reading the Diagnostics

Important fields:

- `selected_polarity`: which polarity was selected
- `selected_reason`: why it was selected
- `threshold_value`: threshold used for segmentation
- `foreground_area_ratio_in_roi`: how much of the ROI became foreground
- `selected_component_bbox`: selected component bounding box in acquisition coordinates
- `candidate_component_count`: number of components after filtering
- `min_local_projection` / `max_local_projection`: selected contour support range
- `distance_to_left_roi_boundary_px` / `distance_to_right_roi_boundary_px`: distance from candidate support to ROI boundary
- `rejected_contact_side`: `left`, `right`, `both`, or `null`
- `rejected_candidate_point_a` / `rejected_candidate_point_b`: debug-only candidate contacts

If `foreground_area_ratio_in_roi` is very large, or the selected component bbox reaches the ROI crop boundary, the detector may have selected background or a fixture-connected region rather than the intended mesh envelope.

## Future Mesh-Envelope Mode

If the goal is to measure the whole open mesh envelope, a later enhancement can remain inside `BalloonEnvelopeDetector` and still preserve the two-detector public contract. Possible internal steps:

- force or strongly prefer `dark_on_light` for dark metal mesh on bright background
- union multiple dark components
- bridge mesh gaps with NumPy morphology
- remove fixture/background components
- construct an external envelope from the mesh support
- then apply the existing ROI-direction A/B contact rule

That would be an internal implementation mode of `BalloonEnvelopeDetector`, not a third public detector.
