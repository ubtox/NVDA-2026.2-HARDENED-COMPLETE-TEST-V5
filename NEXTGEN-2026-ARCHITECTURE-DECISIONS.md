# NVDA NextGen 2026 architecture decisions

These decisions constrain experimental work on `evolution/2026.2-nextgen`. They are intended to prevent short-term experiments from creating long-term architectural debt.

## ADR-001 - Preserve the certified UIAccess desktop core

**Decision:** Keep the proven signed desktop/UIAccess execution model as the authoritative baseline while modern packaging is prototyped.

Rationale:
- A screen reader requires trusted UI interaction across integrity boundaries.
- Windows explicitly reserves `uiAccess=true` for assistive technology and requires trusted signing / secure installation.
- Packaged desktop applications can declare the restricted `uiAccess` capability, but this must be validated end-to-end before replacing the existing installer.

Rule:
- MSIX is a parallel prototype until secure desktop, elevated apps, startup, updates, portable mode and repair/uninstall behavior are proven.
- Never delete the proven installer path simply to obtain package identity.

## ADR-002 - Local Windows AI is a fallback layer, never the accessibility truth source

**Decision:** Accessibility APIs, document semantics and OCR remain authoritative. Generated descriptions are used only when structured accessibility information is unavailable or explicitly requested.

Current Windows AI constraints reviewed in 2026:
- Image Description supports brief, detailed, diagram and accessibility-oriented descriptions.
- Windows AI imaging currently requires package identity / MSIX plus the `systemAIModels` capability.
- Imaging APIs currently require supported modern hardware, including Copilot+ / NPU requirements for the relevant APIs.
- Generated descriptions can be wrong and must be exposed as generated/fallible content.

Architecture:
1. Accessibility tree / document semantics.
2. Existing OCR / deterministic recognition.
3. Local generated description when available and enabled.
4. Clear unsupported fallback when the OS, package identity or hardware capability is absent.

No cloud upload is introduced by default.

## ADR-003 - Add-on isolation uses capability-based out-of-process hosts

**Decision:** The long-term secure add-on architecture is out-of-process and capability based. Synth and braille drivers are the first candidates because they already have clearer IPC-style boundaries.

Windows 11 now documents an experimental `CreateProcessInSandbox` family exported dynamically from `processmodel.dll`. The API can apply AppContainer isolation, low integrity, filesystem/network capability restrictions and Job Object UI restrictions.

Because the API is experimental:
- Resolve it dynamically with `LoadLibraryExW` / `GetProcAddress`.
- Never require it for NVDA startup.
- Keep a compatibility backend for supported Windows versions without the API.
- Treat the sandbox specification version as capability-detected data, not a compile-time invariant.
- Fail closed for the secure add-on host if a requested sandbox permission cannot be enforced.

The secure runtime must default-deny filesystem, registry, network and desktop interaction that an add-on does not need.

## ADR-004 - Python 3.14 is a compatibility laboratory, not a production jump

**Decision:** Production NextGen stays on the validated Python 3.13.15 line until the compatibility lab proves 3.14.

The lab will test:
- CPython 3.14 standard build.
- Free-threaded build separately.
- COM/comtypes behavior.
- Native extensions.
- wxPython.
- synth/braille drivers.
- add-on import/deprecation behavior.
- watchdog and callback thread assumptions.

No free-threading migration is promoted merely because CPython supports it. NVDA's native and COM boundaries must prove correctness first.

## ADR-005 - Draft web standards are feature detected

**Decision:** WAI-ARIA 1.3 support is built as a compatibility suite plus feature-gated mappings.

Rules:
- No browser-version string heuristics when runtime capability/mapping detection is possible.
- Chromium/UIA and Firefox/IA2 must converge at NVDA's semantic speech/braille layer.
- Draft semantics never override stable semantics without browser exposure tests.

## ADR-006 - Performance uses evidence, not timing folklore

**Decision:** Performance changes require deterministic counters where possible, plus trend measurements outside correctness assertions.

Current instrumentation direction:
- exact CI SHA and run identity;
- validation elapsed time;
- unit-test volume/results;
- binary size and SHA-256;
- UIA cross-process call counts on targeted scenarios;
- queue backlog/high-water marks;
- speech queue age/cancellation reason;
- braille refresh/coalescing counters.

Timing thresholds that are sensitive to GitHub-hosted runner load must not become flaky correctness gates.

## ADR-007 - Stable final and NextGen have different risk budgets

`evolution/2026.2-final` remains the certified baseline.

`evolution/2026.2-nextgen` may contain architectural prototypes, but each prototype must be:
- isolated;
- capability gated;
- covered by regression tests;
- removable without breaking startup;
- validated by the complete Evolution build before promotion.

## Upstream absorption policy

Every relevant post-2026.2 NVDA upstream change is classified as one of:

- **absorbed** - equivalent change already exists in Evolution;
- **port** - mature and useful, safe to carry now;
- **adapt** - useful but must be integrated with Evolution's architecture rather than copied;
- **defer** - depends on compatibility-breaking 2027.1 work or insufficiently stable platform APIs;
- **reject** - worse risk/complexity tradeoff than the current implementation.

Known examples from the current audit:

- Lazy protected-typing state query: **absorbed** and regression-tested in NextGen.
- UIA cache batching / current focus validation: **absorbed**.
- 32-bit synth host VC runtime bundling: **absorbed**.
- Add-on transitive import cache cleanup: **absorbed**.
- Built-in speech dictionary pathological-regex fix: **ported**.
- Rectangle conversion compatibility: **port**, pending atomic source patching.
- Win32 x64 / high-DPI owner-drawn menu coordinate repair: **adapt/port after geometry prerequisites and tests**.
- Full-locale startup smoke testing: **port into the compatibility lab**.
- Python 3.14 / free threading: **defer to compatibility lab**.
- Windows local AI image description: **prototype, capability gated**.
- Experimental Windows process sandbox API: **prototype backend only**.
