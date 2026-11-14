RECOMMENDATION: ESCALATE
COMMIT: e20d2cebc4a77cd226513fbde4a3f29b9678a72c
APPROVER: approver

## Summary
- F-01 (T-FRONTEND-SHELL) is complete on this head and in good shape. Round 3 gate PASS, technical, UX, UI and QA reviews PASS, and PMO acceptance PASS all name e20d2ce. All blocking findings (UI-1-1, UI-1-2, UI-1-3, UI-2-1) are verified closed.
- Scope held. All 53 changed files are under `frontend/`. Nothing in `apps/`, `config/`, openapi.json, `design/` or the protected delivery files changed. There is no Start control, bell, account menu, gsap or three.js.
- Policy still needs a person to sign off. This change adds the project's first npm dependency set and an 8,069-line `frontend/package-lock.json`. The `dependency` surface and `package-lock.json` are on the merge policy's always-human lists. Readiness also rated the risk medium (auto-merge allows only low), and 53 files is over the 15-file limit.
- Evidence is UI-only against the contract mock. Real sign-in, CSRF with Django and grant-based permissions are not yet proven; they belong to FE-CONNECT-1.

## Why
If policy allowed it, I would merge this change myself: every acceptance criterion has evidence, and my own spot-checks agree. But it brings in a new third-party dependency tree and lockfile that every later frontend task will inherit. The merge policy says a person must approve that, whatever the review results. Readiness also marked the risk medium and named `dependency` as a surface, so the escalation is expected and is not a quality concern.

## Acceptance criteria
1. Gate passes and dependencies are pinned: met. Round-3 checks.md shows GATE: PASS on e20d2ce: npm ci, lint, typecheck, 89/89 tests and the build all pass. I checked `frontend/package.json` myself: there are no `^` or `~` ranges, and the lockfile is committed.
2. Single style source: met. The drift tests are among the 89 that pass. I re-ran the hex grep from the spec: no hex values in `frontend/src` outside `tokens.css` and `psl-bundle.css`.
3. No runtime font call: met. Builder e2e passed 24/24, and QA saw no requests leave localhost.
4. Client generated and current: met. The schema drift test and the typecheck pass in the gate.
5. Error mapping: met. The vitest client tests pass in the gate. QA checked the 401, 403, 404, network and 500 states in a browser.
6. CSRF header: met. The unit tests pass. PMO's grep found no localStorage, sessionStorage or document.cookie in `src`.
7. Mock matches the contract: met. The contract test passes in the gate. QA independently checked personas, scenarios, CSRF rejection and the 501 response.
8. Navigation follows /me: met. QA walked all three personas and every route. The design-owner decisions of 13 Nov (name only from 720 to 1079px, "name · role" from 1080px) were observed.
9. Phone bar: met. QA and UX checked the menu disclosure, Esc, focus return and navigation at 390px. No horizontal scroll from 390 to 1440px.
10. Frame states: met. QA checked 401, 403, 404, none, loading and Try again.
11. Accessibility: met. axe reported 0 violations in every state the builder's e2e run and QA tried. Skip link, focus ring and reduced motion were checked. Playwright runs outside checks.sh, and build.md records the command and result, as readiness allows.
12. Sample labelling: met. SAMPLE DATA showed in every state QA checked.
13. Mock code out of the app: met. I ran the spec's grep myself: no `mock/` imports in `frontend/src`.
14. No out-of-scope controls: met. QA found no Start, bell or account menu. My grep found no gsap or three in `src` or package.json.

## For the human
Decision needed: do you approve adding this frontend dependency set and its committed lockfile as the base every later frontend task builds on?
- Runtime dependencies: next 16.4.6, react and react-dom 19.3.1, openapi-fetch 0.17.0, and the @fontsource packages (Archivo, IBM Plex Sans, IBM Plex Mono) at 5.3.0.
- Dev tooling: eslint 9.39.5 (now marked deprecated upstream), vitest 5.1.0, jsdom 31.0.1, Playwright 1.65.0, axe-core 4.14.0, openapi-typescript 7.13.0, ajv 8.20.0 and typescript 5.9.3.

Two things to know before you decide:
- **Node version mismatch (TECH-1-5).** jsdom requires Node 24.15 or later. The gate machine runs Node 24.12, so npm prints EBADENGINE warnings, although every test passes. The current plan is to fix this with the Node upgrade. Approving now means accepting that plan.
- **New on-screen copy.** The spec's Assumptions say the wording for the placeholder, no-sections, not-open, signed-out (401) and forbidden (403) states is new; no design board shows these states. It is internal staff wording, not pricing or policy. If you want the design owner to review it, that can happen before or after the merge.

Files to look at:
- `frontend/package.json`
- `frontend/package-lock.json`
- `delivery/features/F-01/readiness.md` (Scope and Risk)
- `delivery/features/F-01/spec.md` (Assumptions)
- `delivery/features/F-01/round-3/acceptance-pmo.md` (the non-blocking items carried forward)

If you approve, merge PR #3 yourself. GitHub cannot record a formal approval from the account that opened it.

## Human decision (13 Nov 2026)
The design engineer (hunchoweb, designated approver) gave a standing delegation: the coordinator decides whether a PR needs them; if not, it merges. For F-01 the coordinator judged the escalation reasons (first pinned dependency set, medium risk, 53 files) reviewed and acceptable with no product, security, money or business-rule decision involved, recorded approval under that delegation, and squash-merged PR #3 as a41d4724a9754a5183ae78fa49c8c3c3e555ed35. No formal GitHub review exists because the PR came from the approver's own account (one-off exception).
