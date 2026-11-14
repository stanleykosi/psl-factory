DECISION: READY
RISK: medium
SURFACES: ui, dependency
PRODUCT-ACCEPTANCE: not-required
BLOCKING-DECISIONS: none
COMMIT: none (round 0, no head yet)
REVIEWER: readiness
AUTHORITY: PMO readiness (delivery step 1)

## Summary
- F-01 = T-FRONTEND-SHELL: the first frontend task of M-1. It has no dependencies (`depends_on: []`, no gates; delivery.md "Unresolved gates: none"). FE-MYWORK, FE-WORKITEM and FE-DECIDE all build on it.
- Gates are met. The client approved the design on 13 Nov 2026 (design/review.json, canvas 1794581312-b166, approver "PSL client approver", CMP-01..24 and all screens). Architecture package v2-reviewed has validation passed and status complete. D-FIRST-FEATURE r2, D-PAGING r2 and D-UPDATES r2 are approved.
- D-API-STYLE and D-AUTH are still `proposed`, owned by the backend developer. A recorded exception covers them: the frontend builds against them as working assumptions (sources/decisions-2026-11-13-v2.md item 3; reviews.json r2 "approve", design engineer). The limit: the shell follows the contract only and does not decide backend sign-in mechanics.
- Outcome: running `npm run dev` in frontend/ against a mock server built from openapi.json shows the approved top bar (desktop) and phone bar. Both are driven by GET /api/v1/me, use the PSL Factory tokens and component CSS, and label sample data.
- Medium risk. This is a new app with new npm dependencies, and it sets the client, error-handling and mock conventions every later frontend task inherits. It touches no data, money, identity logic or migrations, and nothing is deployed.

## Findings
None.

## Scope
**Outcome (one, observable):** a Next.js app in `frontend/` that loads, calls `GET /api/v1/me` through the generated API client against the mock server, and renders the app frame: the desktop top bar and the phone bar, with navigation built from `destinations`. It must pass A-ACCESSIBILITY for that frame at 390px and 1440px.

**In:**
1. **Next.js app in `frontend/`.** TypeScript, with a committed `package-lock.json`. Provide the npm scripts `delivery/checks.sh` runs: `lint`, `typecheck`, `test` and `build`. They must be non-interactive and deterministic, and `npm ci` must work offline-friendly. `checks.sh` is a protected path, so the app must fit it as written.
2. **Design system.** Bring in `design/system/project/tokens.json`, its CSS variables and `design/system/project/components/bundle.css` as the single source of styles. Follow the component READMEs. Do not restyle or re-derive values. Port to React only the components the shell itself uses: the top bar (CMP-01) and the phone bar. Every other component stays CSS-only until a later task needs it.
3. **Top bar (desktop) and phone bar.** Navigation items are My work, Projects, Overview, Assistant and Setup. Show each one only when it is in `/me.destinations`; show the person's name from `/me`. A destination whose screen is not built yet routes to a plain placeholder page using the shared empty-state pattern (STATES boards). Invent no content. Keep the focus ring and reduced-motion rules from bundle.css.
4. **API client generated from `architecture/packages/v2-reviewed/openapi.json`.** Requirements:
   - Typed requests and responses for all operations.
   - Same-origin `/api/v1` base URL.
   - Cookies included.
   - `X-CSRFToken` from `/me.csrf_token` on every write (the D-AUTH working assumption).
   - The `{code, message}` error shape mapped for 401, 403, 404, 409 and 422.
   - No business rules in the client (C-FRONTEND).
5. **Mock server built from the same openapi.json.** It serves at least every M-1 endpoint: E-ME, E-WORK-LIST, E-WORK-ITEM, E-WORK-HISTORY, E-TASK-CLAIM and E-TASK-DECIDE.
   - Fixtures: deterministic sample fixtures that carry `sample: true` wherever the schema has it. Unknown amounts or dates use `unknown: true` with no value.
   - Scenarios: a way to select the 401, 403, 404, 409 and 422 cases so later tasks can test against them.
   - Validation: fixtures must validate against the schemas, which use `additionalProperties: false`.
   - Wiring: it runs locally only, behind the same `/api/v1` path the app calls.
6. **Sample labelling (R-SAMPLE).** The frame shows a visible "Sample data" marker whenever the data in use is mock or sample data.
7. **Tests.**
   - Unit tests for the client's error mapping and CSRF header.
   - A contract test that every mock response validates against openapi.json.
   - Automated accessibility checks (WCAG 2.2 AA) of the frame at 390px and 1440px, plus focus-ring and reduced-motion checks.

   They run under `npm test` inside checks.sh. If a browser-based check cannot run there, say so in build.md and record how it was run instead. Do not leave it unrun.

**Out:**
- The My work page and queues (FE-MYWORK), the work item and history (FE-WORKITEM), and claim/decide (FE-DECIDE).
- The sign-in screen SCR-17, sign-out and the account menu. Their mechanics belong to D-AUTH and the backend.
- The Start work split button and drawer (FE-M2). Omit the button from the shell rather than ship a dead control.
- The notification bell and centre (FE-M4).
- The factory floor, GSAP and three.js (FE-M3).
- Any backend or `apps/api` work, including T-FOUNDATION (the backend developer's task).
- Any deployment or hosting (D-HOSTING is open; no deployment is authorised).
- Real AI or alert providers.

**Task IDs:** T-FRONTEND-SHELL (R-FRONTEND, R-DEVICES, R-SAMPLE).
**Acceptance:** A-ACCESSIBILITY.
**Endpoints:** E-ME is consumed live through the mock. The other M-1 endpoints are covered by the generated client and mock only.

## Risk
I rated it medium rather than low:
- It adds an application and a dependency tree (Next.js, a mock-server library, an OpenAPI type generator, accessibility tooling). The first frontend lint, typecheck, test and build run through `delivery/checks.sh` and must pass in the main checkout's gate.
- The API client and mock encode the cross-layer contract that FE-MYWORK, FE-WORKITEM and FE-DECIDE and FE-CONNECT-1 rely on.

It is not high: the shell holds no business rules, money, identity logic, migrations or concurrency, runs only locally, and the backend stays untouched.

Surfaces:
- `ui`: top bar, phone bar and the approved design system.
- `dependency`: new npm packages and the lockfile.

The surfaces exclude `auth` because the client only attaches the CSRF header defined by the contract and builds no sign-in. They exclude `contract-change` because openapi.json is consumed, not changed.

Product acceptance is not required. The work conforms to the client-approved canvas 1794581312-b166 and adds no new flow, copy or business rule.

## Notes
- `bundle.css` line 1 loads Archivo, IBM Plex Sans and IBM Plex Mono from Google Fonts at runtime. The spec should say whether the shell keeps that network call or self-hosts the same fonts, for example with `next/font`. That is a delivery choice, not a client one.
- I could not run `design.py check` because my role is read-only. The coordinator's design gate (`config.json` `design_gate: required`) should confirm it before build.
- The project's AGENTS.md describes the Django factory build loop (BUILD-STATE.md and the rest). This frontend task's record-keeping follows the delivery workflow in `delivery/`.

## Questions
None.
