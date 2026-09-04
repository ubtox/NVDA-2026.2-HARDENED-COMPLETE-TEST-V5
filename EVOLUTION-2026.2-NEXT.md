# NVDA 2026.2 Evolution Next

This branch is intentionally separated from release-candidate stabilization.
Its purpose is to evolve NVDA as a system rather than accumulate isolated fixes.

## Engineering rules

1. RC branches remain stabilization-only.
2. Evolution work is grouped into coherent architectural tracks.
3. Every core change must include regression tests or measurable validation.
4. Performance changes must preserve accessibility semantics first.
5. No release-labelled artifact is produced from this branch.
6. A track is promoted toward release only after full build, unit tests, quality checks and targeted stress validation pass.

## Track 1 - Core scheduler and event pipeline v2

Goal: keep focus, input and speech-critical work responsive during UIA/IA2 event storms.

Planned work:
- Real priority lane for latency-sensitive main-thread work.
- Conservative coalescing of redundant high-frequency non-focus events.
- Fairness rules so normal work cannot starve.
- Queue backlog diagnostics and latency measurements.
- Stress tests covering large event bursts and focus transitions.

Acceptance criteria:
- Focus-critical work bypasses an existing normal-event backlog.
- Normal queued work still executes deterministically.
- No event loss for focus, caret, live-region or user-input semantics.
- Unit and system validation remain green.

Status:
- Priority event lane implemented.
- Priority scheduling unit tests added.
- Normal event work bounded per pump cycle so one event backlog cannot monopolize the core thread.
- Fair-pump slicing unit tests added.
- NV Access cooperative LiveText flood handling ported exactly, yielding between announcement batches and bounding stale terminal output.
- Conservative coalescing implemented for duplicate payload-free `locationChange` and `visibleDataChange` events targeting the same object.
- Six regression tests protect coalescing boundaries: payload events, caret events, separate objects and re-queue after callback completion remain uncoalesced.
- Per-pump queue diagnostics now capture priority/normal backlog depth, processed counts, maximum queue wait, pump duration and remaining normal backlog.
- Pressure diagnostics are logged only when backlog or latency thresholds are exceeded, avoiding normal-log noise.
- Deterministic stress coverage now includes 1,000-event redundant-state storms, preservation of priority `gainFocus`, and multi-slice draining of large normal backlogs without loss or reordering.
- The scheduler/event-pipeline changes, telemetry and stress suite passed the full Evolution validation pipeline on commit `39b44de7c45ecbd1b2ef4d348217e3e82377f340`.

## Track 2 - UI Automation pipeline v2

Goal: reduce hangs, duplicate work and expensive cross-process UIA calls.

Planned work:
- Centralize transient UIA failure handling.
- Reduce duplicate property/event processing before object construction where safe.
- Prefer batched/cached property retrieval for hot paths.
- Add bounded recovery around disconnected providers.
- Add regression tests for frozen or disappearing providers.

Acceptance criteria:
- Fewer redundant UIA object/property fetches under synthetic event storms.
- No regression in focus, live regions, text controls, Chromium, Edge, Office or Windows shell navigation.

Status:
- NV Access hung-application fast-fail safeguards (#20168) ported by guarded source hunks without overwriting fork-specific UIA hardening.
- UIA events now use cached window information to reject events from applications Windows marks as not responding.
- MSAA events and higher-API object construction now avoid windows belonging to hung applications.
- The high-frequency UIA text-change path uses the cached class name rather than a live cross-process fetch.
- Official hung-window guard regression tests retained in a separate test module alongside the fork's existing UIA normalization tests.
- NV Access watchdog cancellation safeguards (#20170) ported for blocking UiaHasServerSideProvider and Word in-process text calls.
- NV Access SelectionContainer provider-failure handling (#20255) ported: a provider `COMError` is treated as a missing selection container instead of aborting the entire focus-speech path.
- A dedicated regression test forces a SelectionItem provider `COMError` and verifies the UIA object boundary returns `None` cleanly.
- The existing `_getUIACacheablePropertyValue_handlesCOMErrors` boundary for UIA state retrieval was audited and retained; no duplicate port was needed.
- Broader disconnected-provider recovery, property batching and event-storm measurements remain planned.

## Track 3 - Speech and braille responsiveness

Goal: prevent stale output from competing with current user context.

Planned work:
- Expand cancellation semantics for obsolete queued output.
- Prioritize focus/input-triggered output over stale background announcements.
- Review braille refresh scheduling for duplicate refresh suppression.
- Add deterministic tests for rapid focus and text changes.

Acceptance criteria:
- Obsolete output is cancelled without suppressing the final current state.
- Braille and speech remain synchronized with current focus/review context.

Status:
- LiveText burst reporting is cooperative and cancellable rather than synchronously monopolizing the main thread.
- General speech and braille stale-output policies remain planned.

## Track 4 - Resilience and self-recovery

Goal: recover cleanly from provider failures without restart loops or silent hangs.

Planned work:
- Structured failure domains around UIA, IA2, synth and braille-driver boundaries.
- Bounded retry and fallback policies.
- Better watchdog diagnostics for slow main-thread operations.
- Recovery tests for provider disconnects and driver failures.

Acceptance criteria:
- Recoverable subsystem failures do not crash or deadlock the whole process.
- Repeated fatal failure is surfaced clearly rather than causing uncontrolled restart loops.

Status:
- Blocking UIA and Word accessibility calls covered by the existing watchdog cancellation mechanism where upstream identified uncancellable cross-process calls.
- Hung UIA/MSAA applications are rejected early instead of repeatedly entering blocking provider calls.
- UIA SelectionItem provider disconnections no longer propagate through `selectionContainer` and silence the whole focus event.
- Magnifier repeated-error recovery and COM/UIA disconnection handling were audited and are already present in the Evolution baseline, so no redundant port was applied.
- General subsystem failure-domain and retry policy work remains planned.

## Track 5 - Security boundary hardening

Goal: make lock-screen and secure-desktop boundaries explicit and testable across object layers.

Planned work:
- Apply security checks consistently to NVDAObject and TreeInterceptor paths.
- Audit global plugin and add-on exposure around secure contexts.
- Add targeted tests for lock-screen object traversal and cached objects.

Acceptance criteria:
- No object content from below the lock screen is exposed through alternate object layers.
- Security regression tests run in the normal evolution validation pipeline.

Status:
- NV Access TreeInterceptor lock-screen boundary hardening (#20678) ported byte-for-byte for source and unit tests.
- TreeInterceptors are resolved through their root NVDAObject for lock-screen checks, closing the alternate object-layer gap.
- Global plugin/add-on secure-context exposure audit and broader cached-object security tests remain planned.

## Track 6 - Build, quality and observability

Goal: make performance and reliability regressions visible before promotion.

Planned work:
- Dedicated evolution CI isolated from RC builds.
- Full Ruff, format, Pyright, unit, source, dist and launcher checks.
- Event-pipeline stress suite.
- Reproducible artifact hashes and validation evidence.
- Performance baselines for event backlog and selected hot paths.

Acceptance criteria:
- Every evolution commit is validated independently from RC.
- No evolution artifact is presented as a release candidate.

Status:
- Dedicated Evolution CI is active and isolated from RC validation.
- Full build, unit, Ruff, format, Pyright, source, dist and launcher validation is executed by LAB-BUILD.
- Evolution binaries identify themselves as `2026.2.0dev-evolution`; CI rejects ambiguous installer identities.
- Event-pipeline stress coverage and queue-pressure diagnostics are active in the normal unit/validation pipeline.
- Quantitative performance baselines and trend comparison remain planned.

## Promotion model

`rc/2026.2-hardened-rc2` remains the stable candidate line.

`evolution/2026.2-next` receives architectural work.

Only completed, validated tracks should later be integrated into a future release branch. This prevents experimental core changes from destabilizing the current RC while allowing substantial development to continue.