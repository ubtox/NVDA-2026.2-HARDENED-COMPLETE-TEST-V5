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

## Track 5 - Security boundary hardening

Goal: make lock-screen and secure-desktop boundaries explicit and testable across object layers.

Planned work:
- Apply security checks consistently to NVDAObject and TreeInterceptor paths.
- Audit global plugin and add-on exposure around secure contexts.
- Add targeted tests for lock-screen object traversal and cached objects.

Acceptance criteria:
- No object content from below the lock screen is exposed through alternate object layers.
- Security regression tests run in the normal evolution validation pipeline.

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

## Promotion model

`rc/2026.2-hardened-rc2` remains the stable candidate line.

`evolution/2026.2-next` receives architectural work.

Only completed, validated tracks should later be integrated into a future release branch. This prevents experimental core changes from destabilizing the current RC while allowing substantial development to continue.
