# File Index and Usage

This index explains the purpose of every file in the starter pack.

## Root files

### `README.md`

Overview of the starter pack and step-by-step usage instructions.

Use it yourself before opening Codex.

### `AGENTS.md`

Persistent repository-level instructions for Codex.

Use it by placing it in the root of the new repository. Codex should read it automatically before work. It defines project rules, cross-platform constraints, detection rules, and definition of done.

### `00_CODEX_START_HERE.md`

The first file Codex should read after `AGENTS.md`.

Use it to orient Codex to the clean-start goal and the non-negotiable detection contract.

### `.gitignore`

Ignores Python/Node build outputs, local configs, runtime artifacts, logs, and camera SDK binaries.

Use it unchanged at the root of the new repository.

### `.codex/config.example.toml`

Optional example for repo-local Codex settings.

Use it only if you want to create `.codex/config.toml` later. It is not required.

## Docs

### `docs/01_PRODUCT_REQUIREMENTS.md`

Defines product purpose, users, workflows, scope, non-goals, target families, and platform requirement.

Use it as the product requirements document.

### `docs/02_DETECTION_CONTRACT.md`

Defines A/B points, ROI requirements, target family behavior, failure states, quality score, and diagnostics.

Use it as the highest-priority vision behavior contract.

### `docs/03_ARCHITECTURE_TECH_ROUTE.md`

Defines Web + Python architecture, recommended backend/frontend stack, layer responsibilities, runtime modes, storage and config strategy.

Use it to guide project design and dependency choices.

### `docs/04_PROJECT_STRUCTURE.md`

Defines the target repository tree and folder responsibilities.

Use it when asking Codex to scaffold or refactor the project layout.

### `docs/05_API_CONTRACT.md`

Defines initial HTTP endpoints and request/response payloads.

Use it when implementing backend routes and frontend API calls.

### `docs/06_DATA_MODEL_CONTRACT.md`

Defines enums and Pydantic-style models for coordinates, ROI, frame refs, recipes, detection results, and run samples.

Use it before writing backend models.

### `docs/07_CROSS_PLATFORM_REQUIREMENTS.md`

Defines macOS/Windows portability rules and hardware-boundary constraints.

Use it to prevent platform-specific code from leaking into core logic.

### `docs/08_DEVELOPMENT_PLAN.md`

Defines implementation phases from scaffold to the two target-family detectors, setup UI, run service, hardware, and exports.

Use it as the roadmap for Codex tasks.

### `docs/09_TEST_PLAN.md`

Defines required unit, synthetic vision, API, frontend, and manual smoke tests.

Use it when asking Codex to write or review tests.

### `docs/10_ACCEPTANCE_CHECKLIST.md`

Defines review checklist for generated code.

Use it before accepting Codex diffs.

### `docs/11_OPEN_QUESTIONS.md`

Lists unresolved product and hardware questions with default assumptions.

Use it to avoid blocking early development.

## Config examples

### `configs/profiles/dev_mock.yaml`

Mock mode profile. No hardware required.

Use it as the first runtime profile.

### `configs/profiles/dev_offline.yaml`

Offline image-folder profile.

Use it when testing with saved image frames.

### `configs/profiles/dev_lab.example.yaml`

Example real-lab profile for future Hik MVS integration.

Do not put machine-specific paths here. Copy to `configs/local/*.yaml` later.

### `configs/recipes/balloon_envelope_default.yaml`

Default recipe for `BalloonEnvelopeDetector` whole-envelope targets.

Use it for `balloon_envelope` setup detection.

### `configs/recipes/wire_strip_default.yaml`

Default recipe for `WireStripDetector` wire/strip contour targets.

Use it for `wire_strip` setup detection.

## Prompts

### `prompts/01_INITIAL_SCAFFOLD_PROMPT.md`

First prompt to paste into Codex after copying this pack into a new empty repo.

Use it to generate the initial project skeleton.

### `prompts/02_PHASE1_VISION_PROMPT.md`

Prompt for implementing the first tested balloon and wire/strip detectors.

Use it after the scaffold and core models are working.

### `prompts/03_PHASE2_WEB_SETUP_PROMPT.md`

Prompt for connecting backend detection to a minimal frontend setup flow.

Use it after synthetic detector tests for both target families pass.

### `prompts/04_CODE_REVIEW_PROMPT.md`

Prompt for asking Codex to review the generated repository against the contracts.

Use it after each major phase.
