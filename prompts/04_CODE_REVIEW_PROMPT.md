# Prompt 04 — Code Review

Review the current repository against:

- `AGENTS.md`
- `docs/02_DETECTION_CONTRACT.md`
- `docs/07_CROSS_PLATFORM_REQUIREMENTS.md`
- `docs/10_ACCEPTANCE_CHECKLIST.md`

Look for:

- old-project references
- platform-specific paths
- SDK imports outside adapters
- API routes containing business/vision logic
- frontend computing formal A/B points
- `wire_strip` endpoint detection mistakenly added
- detection result without explicit status
- missing tests for changed behavior

Return:

1. Critical issues.
2. Suggested fixes.
3. Tests to add.
4. Whether the project is ready for the next phase.
