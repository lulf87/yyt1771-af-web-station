# 11 — Open Questions

These are intentionally not blockers for the first scaffold. Codex should use the default assumptions below unless the user updates the requirements.

## Actual camera model

Default assumption:

- Real camera integration is delayed.
- Use camera interface plus mock/offline sources first.

Open:

- Exact Hik camera model.
- Pixel format.
- Desired acquisition ROI.
- Frame rate target.
- Exposure/lighting controls.

## Image polarity

Default assumption:

- Recipe supports `polarity: auto`.

Open:

- Is the target darker or brighter than background in real images?
- Does polarity change between balloon and wire targets?

## Temperature input

Default assumption:

- Temperature is optional in early samples.
- Run sample allows `temperature_c: null`.

Open:

- Temperature device model.
- Sampling rate.
- Timestamp synchronization method.

## AF analysis

Default assumption:

- Early project stores pixel distance curve only.
- AF analysis methods are implemented later.

Open:

- Exact AF-95 rule.
- Exact tangent method rule.
- Required report format.

## Lens distortion and calibration

Default assumption:

- No geometric calibration in first version.
- Use acquisition pixel coordinates directly.

Open:

- Is lens distortion significant for the measurement region?
- Is any correction required before detection?

## Production packaging

Default assumption:

- Development mode first.

Open:

- Packaging as executable.
- Service startup method.
- Deployment folder conventions on macOS/Windows.
