# NVDA NextGen 2026-2028 roadmap

## Mission

Push the NVDA 2026.2 Evolution codebase as far as is technically defensible in 2026, while preserving accessibility semantics, security, recoverability and maintainability.

The certified baseline remains immutable. Experimental and architectural work belongs on `evolution/2026.2-nextgen` and is promoted only after full validation.

Certified starting point: `c7101ea978e69cdcf4ac8c006282c4c2b9dc52a8`.

## External engineering signals reviewed

- NV Access 2026 roadmap: stability, security, braille, import/export, installer modernization, magnifier, corporate mode, secure add-on runtime, OCR, Office UIA, Remote E2E encryption, ARIA compliance, local image description and UI element recognition.
- NVDA upstream started the 2027.1 development cycle as a compatibility-breaking release on 2026-09-04.
- WAI-ARIA 1.3 is an active 2026 Working Draft; support must therefore be feature-detected and regression-tested rather than hard-coded around unstable assumptions.
- Windows AI APIs now expose local image-description capabilities, including an accessibility-oriented description mode. Current Windows requirements tie these APIs to modern package identity/MSIX and supported Copilot+ hardware.
- Python 3.14 is stable in 2026 and officially supports free-threaded builds and multiple interpreters, but NVDA's COM, native extensions, add-ons and driver ecosystem make an immediate production migration inappropriate without a compatibility lab.
- Windows documentation continues to center UI Automation for modern app accessibility and provides UIA Verify / Accessibility Insights for automated accessibility validation.

## Non-negotiable engineering rules

1. No speculative optimization may weaken focus, caret, live-region, password/security, braille or speech semantics.
2. Every core behavior change gets deterministic regression coverage.
3. Performance work gets measurements before and after the change.
4. Blocking cross-process work must have bounded cancellation, quarantine or fallback behavior where technically possible.
5. The certified final branch is never used as an experiment branch.
6. Add-on compatibility breaks are isolated to an explicit compatibility-breaking line.
7. Local AI features are opt-in, local-first, capability-gated and never silently replace authoritative accessibility APIs.
8. Experimental APIs and draft standards use runtime feature detection and safe fallback.
9. No release promotion occurs without Ruff, formatting, Pyright, unit tests, SCons source/dist/launcher, installer identity and artifact hashing.

# Track A - Core latency architecture v3

Goal: make user-input and focus response deterministic even during event storms and bad providers.

Work:
- Extend queue telemetry into quantitative latency distributions and backlog high-water marks.
- Define latency classes for focus/input, caret, live region, background state and maintenance work.
- Add bounded processing budgets per pump with starvation protection.
- Add provider-level temporary quarantine after repeated blocking/disconnection failures.
- Add synthetic stress suites for 1k/10k event storms and rapid foreground switching.

Promotion criteria:
- No loss/reordering of protected semantic events.
- Focus/input lane remains responsive during background floods.
- Normal lane drains fairly after pressure disappears.

# Track B - UIA / Office / modern Windows pipeline

Goal: minimize synchronous cross-process UIA cost and tolerate broken providers.

Work:
- Centralize transient COM/UIA failure policy.
- Expand cache-request batching on hot property paths.
- Avoid duplicate object construction before event filtering when safe.
- Add disconnected-provider recovery tests.
- Expand Word and PowerPoint UIA coverage while retaining safe legacy fallbacks.
- Test WinUI 3, Windows App SDK, WebView2 and packaged desktop applications explicitly.

Promotion criteria:
- Lower property-call count on hot paths.
- No regression in Edge/Chromium, Firefox, Office, Windows shell, Qt or WinUI.

# Track C - Web standards 2026+

Goal: move ahead of current production ARIA support without betting the core on draft behavior.

Work:
- Build an ARIA 1.3 compatibility test inventory.
- Add feature-gated handling for newly exposed roles/states/properties as browser mappings stabilize.
- Expand automated regression cases for aria-activedescendant, live regions, name/description computation, grids, comboboxes and complex editable widgets.
- Keep Chromium/UIA and Firefox/IA2 behavior aligned at the speech/braille semantic layer.

# Track D - Speech engine vNext

Goal: current context always wins over stale output.

Work:
- Introduce explicit speech priority classes and stale-output cancellation rules.
- Implement native bounded speech history beyond only the last utterance.
- Add deterministic rapid-focus/rapid-text tests.
- Preserve secure-field masking throughout history and repeat paths.
- Add instrumentation for speech queue age and cancellation reason.

# Track E - Braille vNext

Goal: braille becomes a first-class low-latency output pipeline rather than a follower of speech.

Work:
- Complete sleep/release semantics so a display can be handed to another host without quitting NVDA.
- Improve HID/BLE transport recovery and diagnostics.
- Keep braille synchronized during Say All and browse-mode movement.
- Expand DotPad/multiline architecture for spatial and font-attribute presentation.
- Add duplicate-refresh suppression metrics and driver fault recovery tests.

# Track F - Vision / Magnifier vNext

Goal: make the built-in magnifier competitive as an integrated low-vision tool.

Work:
- Keyboard panning.
- Docked/fixed window modes where technically stable.
- Advanced caret, focus and mouse tracking.
- Immediate settings preview with rollback on cancel.
- Gesture-conflict review so magnifier features do not consume disproportionate global shortcuts.

# Track G - Local AI accessibility layer

Goal: use local ML only where accessibility APIs cannot provide the information.

Work:
- Prototype Windows local image-description APIs behind capability detection.
- Support brief/detailed/diagram/accessibility description modes.
- Keep OCR and authoritative accessibility-tree text ahead of generated descriptions.
- Explore local inaccessible-control recognition as an explicit fallback layer.
- Never send content to a cloud service by default.
- Clearly mark generated descriptions as generated and fallible.

Dependencies:
- Modern Windows capability detection.
- Packaging/MSIX investigation because current Windows AI image APIs require package identity/capabilities.
- Copilot+ / NPU availability fallback.

# Track H - Installer, packaging and enterprise

Goal: modern deployment and predictable fleet management.

Work:
- Prototype MSIX/sparse-package deployment without deleting the proven installer path prematurely.
- Evaluate WiX as a fallback/transition path where MSIX constraints conflict with screen-reader requirements.
- Build import/export for configuration and user data with schema/version validation.
- Add corporate policy mode for locked settings, update policy and controlled add-on deployment.
- Add reproducible install/uninstall/upgrade tests.

# Track I - Add-on security and isolation

Goal: keep extensibility while reducing the blast radius of untrusted add-ons.

Work:
- Design a capability-based out-of-process add-on host.
- First isolate synth and braille add-ons where IPC boundaries are clearest.
- Define explicit permissions/capabilities and deny dangerous ambient access by default in the secure runtime.
- Preserve a compatibility lane for trusted legacy add-ons during migration.
- Investigate Python 3.14 subinterpreters/free-threaded builds only inside the compatibility lab until COM/native-extension/add-on behavior is proven.

# Track J - Remote access security

Goal: minimize relay trust and harden remote-control boundaries.

Work:
- End-to-end encryption design and test vectors.
- Explicit peer identity verification.
- Replay/downgrade resistance.
- Secure-desktop and lock-screen policy tests.
- Network fault and reconnect stress tests.

# Track K - Self-recovery and fault domains

Goal: recover individual subsystems without restarting the whole screen reader.

Work:
- Failure domains for UIA, IA2, synth, braille, vision, OCR/AI and remote.
- Bounded retries with backoff and circuit-breaking.
- Crash-loop detection and safe-mode recovery.
- Structured diagnostics that identify the provider/driver and operation causing a stall.

# Track L - Quality, compatibility lab and observability

Goal: make regressions visible before users experience them.

Work:
- Record per-stage CI duration and artifact metadata.
- Add repeatable scheduler/UIA/speech/braille performance scenarios.
- Build a compatibility matrix for supported Windows builds, Office, Edge/Chromium, Firefox, Qt, WinUI 3/WebView2 and representative braille drivers.
- Add automated UIA verification scenarios where Windows tooling permits unattended execution.
- Track performance trends separately from correctness gates so noisy timing does not create flaky releases.
- Add mutation/fuzz/property-based tests only around parsers, protocol boundaries and pure functions where deterministic reproduction is possible.

## 2026 execution order

### Wave 1 - Foundation
1. CI performance/latency evidence.
2. Provider failure-domain instrumentation.
3. UIA cache/call-count reduction with regression tests.
4. Speech stale-output policy and bounded speech history.
5. Braille transport/release robustness.

### Wave 2 - User-visible modernization
1. Magnifier panning/tracking/settings preview.
2. Configuration import/export.
3. Office UIA expansion.
4. ARIA 1.3 compatibility suite.
5. MSIX/sparse-package prototype.

### Wave 3 - Security architecture
1. Corporate mode foundations.
2. Secure add-on runtime prototype.
3. Remote E2E prototype and test vectors.
4. Safe-mode / crash-loop recovery.

### Wave 4 - Forward-looking local intelligence
1. Windows local image-description prototype.
2. Model/capability selection and fallback policy.
3. Inaccessible UI recognition research prototype.
4. Multi-line braille spatial/attribute experiments.

## Stop conditions

A change is rejected or reverted when:
- accessibility semantics regress;
- the measurable gain is negligible relative to complexity;
- it relies on unstable APIs without feature detection;
- it creates unbounded background work;
- it weakens lock-screen, secure-desktop, password or remote-security boundaries;
- it creates a compatibility break outside the designated breaking-development line;
- it cannot be validated deterministically enough to maintain.

## Definition of 'ahead by two years'

The objective is not a marketing version number. The branch is considered materially ahead when it combines:
- deterministic low-latency core behavior under hostile event/provider conditions;
- modern UIA/Office/Web standards support;
- first-class speech, braille and magnifier pipelines;
- secure deployment/add-on/remote boundaries;
- local capability-gated AI fallbacks;
- measurable performance and compatibility evidence on every promoted change.
