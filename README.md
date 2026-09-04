# NVDA 2026.2 LAB

This repository contains the NVDA 2026.2 Hardened V5 laboratory tree and its validation history.

The active NVDA source tree is:

`NVDA-2026.2-HARDENED-SOURCE-V5/`

The repository root intentionally keeps the previous validation evidence under `VALIDATION-RUNS/` and patch backups. New root-level LAB entry points make the repository directly buildable without having to know the internal directory layout.

## Current LAB objective

Produce a reproducible, testable NVDA 2026.2 LAB build while keeping failures visible instead of hiding them.

Known validation evidence currently includes successful Chrome and VS Code compatibility runs. Remaining symbol-pronunciation failures must be treated as validation issues until a core regression is demonstrated.

## Requirements

- Windows 11 recommended
- CPython 3.13.13 x64
- `uv`
- Visual Studio 2022/2026 build tools with the NVDA C++/SDK components

The source tree itself contains the upstream NVDA development documentation and pinned project dependencies.

## One-command LAB validation/build

From PowerShell at the repository root:

```powershell
.\LAB-BUILD.ps1
```

Default mode performs dependency synchronization, Python architecture/version verification, Ruff checks, formatting checks and a serial `scons source` build.

Build a portable distribution:

```powershell
.\LAB-BUILD.ps1 -Mode Dist
```

Build the NVDA LAB launcher:

```powershell
.\LAB-BUILD.ps1 -Mode Launcher
```

Run the complete source + dist + launcher sequence:

```powershell
.\LAB-BUILD.ps1 -Mode All
```

Use `-Parallel` only after a serial build is known to pass.

## Run NVDA from source

After a successful source build:

```powershell
.\LAB-RUN.ps1
```

Additional NVDA command-line arguments can be passed through, for example:

```powershell
.\LAB-RUN.ps1 -NvdaArgs @("--debug-logging")
```

## Quality rule

`main` is the active LAB line. Changes should preserve a fail-closed workflow: build/test failures remain failures, generated artifacts are not treated as proof of correctness, and core NVDA changes require a reproducible reason and validation.