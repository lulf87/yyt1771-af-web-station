# 00 — Codex Start Here

You are building a new project from zero.

Do not inspect, reference, import, or copy any previous project. The only product context is contained in this repository's starter documents.

## Goal

Create a cross-platform Web + Python application for supporting visual AF-point analysis in a YY/T 1771-style workflow.

The system captures or replays image frames of a test object during a thermal recovery process, extracts two contour-based A/B measurement points inside a rotated ROI, computes Euclidean pixel distance between those two points, and stores the resulting time/temperature/distance samples for analysis and export.

## First implementation objective

The first implementation must be useful without hardware:

- backend runs locally
- frontend runs locally
- mock/offline image source works
- rotated ROI can be represented
- synthetic detector tests for both target families pass
- no real camera SDK required

## Non-negotiable detection contract

A/B points are contour contact points selected by the target-specific detector using the ROI measurement direction.

Given:

- current frame
- rotated ROI
- target family
- ROI measurement direction

The selected target-specific detector must:

1. Be either `BalloonEnvelopeDetector` or `WireStripDetector`.
2. Extract the valid target contour inside the ROI.
3. Select the contour contact point on the smaller projection side as A.
4. Select the contour contact point on the larger projection side as B.
5. Compute `distance_px` as Euclidean distance between A and B.
6. Return explicit failure status if the contact points are not reliable.

Do not create a third public detector in the initial version.

Target families:

- `balloon_envelope`: use outer envelope and ignore internal mesh/texture.
- `wire_strip`: use visible strip/wire-like contour inside ROI; do not search for physical endpoints.

## First Codex task

Use `prompts/01_INITIAL_SCAFFOLD_PROMPT.md` as the first prompt.

Do not start by implementing every feature. Start by creating the project skeleton, typed contracts, tests, and minimal synthetic paths for both target-specific detectors.
