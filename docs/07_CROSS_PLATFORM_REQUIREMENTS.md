# 07 — Cross-platform Requirements

The project must support both macOS and Windows.

## Principle

Core code is cross-platform. Platform-specific code is isolated at hardware and local configuration boundaries.

## Must be cross-platform

- API routes
- services
- data models
- geometry
- coordinate transforms
- vision algorithms
- storage paths
- frontend UI
- tests for mock/offline mode

## May be platform-specific

- camera SDK runtime discovery
- dynamic library loading
- real camera device enumeration
- serial device names
- local profile files
- local startup scripts if optional

## Forbidden hard-coded assumptions

Do not hard-code:

- `/tmp`
- `/dev/tty.*`
- `/Users/...`
- `C:\...`
- local SDK install paths
- shell-only commands like `bash`, `rm`, `cp`, `grep`
- OS path separators

## Required practices

- Use `pathlib.Path` for paths.
- Store machine-specific values in ignored local configs.
- Use Python module entrypoints.
- Use cross-platform npm scripts.
- Do not require admin permissions for mock/offline mode.
- Do not import real camera SDK at backend package import time.
- Lazy-load hardware SDK only when selected profile requires it.

## Windows-specific cautions

- Do not rely on POSIX fork behavior.
- Avoid Unix signal assumptions.
- Avoid shell-specific subprocess calls.
- Keep filenames portable.
- Read serial ports from config, e.g. `COM3`.
- Ensure tests do not rely on case-sensitive paths.

## macOS-specific cautions

- Do not hard-code `/Users/...`.
- Do not assume Homebrew paths.
- Do not assume camera SDK paths.
- Read all local paths from config or environment.

## Config pattern

Committed examples:

```text
configs/profiles/dev_mock.yaml
configs/profiles/dev_offline.yaml
configs/profiles/dev_lab.example.yaml
```

Ignored local machine files:

```text
configs/local/mac_lab.yaml
configs/local/windows_lab.yaml
```

## Required runtime modes

### Mock mode

Must run on macOS and Windows without hardware.

### Offline mode

Must run on macOS and Windows using a configured folder of images.

### Lab mode

May require hardware SDK and local config. Failure to load lab hardware must not break mock/offline mode.
