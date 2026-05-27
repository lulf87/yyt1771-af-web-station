# 04 — Project Structure

This file defines the intended repository layout for the new project.

## Target layout

```text
yyt1771-af-web-station/
  README.md
  AGENTS.md
  pyproject.toml
  package.json
  .gitignore

  configs/
    profiles/
      dev_mock.yaml
      dev_offline.yaml
      dev_lab.example.yaml
    recipes/
      balloon_envelope_default.yaml
      wire_strip_default.yaml
    local/
      .gitkeep

  backend/
    src/
      yyt1771_af/
        __init__.py
        main.py

        api/
          __init__.py
          health.py
          camera.py
          setup.py
          runs.py
          analysis.py

        services/
          __init__.py
          camera_service.py
          setup_service.py
          run_service.py
          analysis_service.py

        core/
          __init__.py
          models.py
          geometry.py
          coordinates.py
          statuses.py
          config.py

        vision/
          __init__.py
          preprocessing.py
          segmentation.py
          roi_ops.py
          balloon_envelope_detector.py
          wire_strip_detector.py

        camera/
          __init__.py
          base.py
          mock.py
          offline.py
          hik_mvs.py

        storage/
          __init__.py
          artifact_store.py
          run_store.py

        report/
          __init__.py
          export_csv.py
          export_xlsx.py
          export_png.py

    tests/
      core/
        test_geometry.py
        test_coordinates.py
        test_models.py
      vision/
        test_balloon_envelope_detector_synthetic.py
        test_wire_strip_detector_synthetic.py
      api/
        test_health.py
        test_setup_detect.py

  frontend/
    index.html
    package.json
    tsconfig.json
    vite.config.ts
    src/
      main.tsx
      api/
        client.ts
        types.ts
      pages/
        SetupPage.tsx
        RunPage.tsx
        AnalysisPage.tsx
      components/
        FrameCanvas.tsx
        RoiEditor.tsx
        DetectionOverlay.tsx
        TargetFamilySelector.tsx
        StatusPanel.tsx
      geometry/
        transforms.ts
      styles/
        app.css

  docs/
    01_PRODUCT_REQUIREMENTS.md
    02_DETECTION_CONTRACT.md
    03_ARCHITECTURE_TECH_ROUTE.md
    04_PROJECT_STRUCTURE.md
    05_API_CONTRACT.md
    06_DATA_MODEL_CONTRACT.md
    07_CROSS_PLATFORM_REQUIREMENTS.md
    08_DEVELOPMENT_PLAN.md
    09_TEST_PLAN.md
    10_ACCEPTANCE_CHECKLIST.md
    11_OPEN_QUESTIONS.md
```

## Rules

### No ambiguous shared folders

Avoid vague names such as:

- `utils`
- `common`
- `misc`
- `helpers`

Use domain-specific names instead:

- `geometry`
- `coordinates`
- `segmentation`
- `roi_ops`
- `artifact_store`

### Backend package root

The backend import package is:

```text
yyt1771_af
```

Do not name the Python package `src`.

### Frontend and backend separation

Frontend code must not import backend Python code.

Backend code must not depend on frontend build artifacts except for optional static serving in a later production mode.

### Configs

Committed examples are allowed.

Machine-specific files must be ignored:

```text
configs/local/*.yaml
```

### Tests

Backend tests live under:

```text
backend/tests/
```

Frontend tests live near frontend source or under:

```text
frontend/src/**/*.test.ts
```
