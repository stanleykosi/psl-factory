# Bring frontend fixtures and tests up to API 1.24.0 so the build is green

> Tasks: none (conformance hotfix). Architecture: contracts/psl-factory.openapi.json and frontend/src/api/live-schema.d.ts at API 1.24.0. Design: none; screens: none.

## Summary
- `npx tsc --noEmit` fails on main b8542c79 because 1.24.0 makes `positions` required on GET /me and `url` and `available` required on each `destinations[]` entry.
- Update the mock and test fixtures to those shapes and keep every existing assertion.
- Change non-test code only where the types force it. Behaviour that uses the new fields is F-67.

## Context
- Failing now: `frontend/tests/shell-live.test.tsx:95` builds a /me object with no `positions` and destinations with only `key`, `title`, `django_url`.
- Mock /me fixtures: `frontend/mock/fixtures/me.*.json` (admin, hr, hr_lead, pmo_lead, finance_lead, ceo, pm), served by `frontend/mock/server.mjs`. Other fixtures carry `django_url`: `frontend/mock/demo-projects.mjs`, `mock/fixtures/projects/*.json`, `E-PROJECT.json`. Check each against its schema and change only those that fail.
- Ajv checks against the contract: `frontend/tests/mock-live-me.test.ts` and `mock-live-projects.test.ts`.
- 1.24.0 shapes: destination `{key, title, django_url, url: string, available: boolean}`. Position `{role: pmo-lead|finance-lead|hr|admin|cto|ceo, mode: member|lead|standalone|administrator, name, area, focus, workspace, team: string|null, invite_url: string|null, manage_url: string|null}`. Source: `live-schema.d.ts` around lines 5100-5125.

## Contract
No endpoint or payload changes. The fixtures must equal what API 1.24.0 returns.
- Every `me.*.json` has `positions`. Use `[]` for personas with no position, and a realistic entry where the persona's role maps to one (for example pmo_lead gets `pmo-lead`).
- Every destination gets `url` and `available`. Reuse the existing `django_url` value or the mock's existing route as `url`. Use `available: true` unless the persona truly cannot open it.
- `tests/shell-live.test.tsx` fixtures get the same fields. No new UI states.

## Lanes
- Frontend lane owns all of it: `frontend/mock/**` and `frontend/tests/**`, plus any type-forced file under `frontend/src/**`.
- No backend lane and no shared files. `live-schema.d.ts`, `contracts/` and protected paths stay unchanged.

## Acceptance criteria
1. Lint passes. verify: `cd frontend && npm run lint` exits 0.
2. Types pass. verify: `cd frontend && npm run typecheck` exits 0, and `tests/shell-live.test.tsx:95` no longer errors.
3. Tests pass. verify: `cd frontend && npm test` exits 0, including `mock-live-me.test.ts`, `mock-live-projects.test.ts` and `shell-live.test.tsx`.
4. The build passes. verify: `cd frontend && npm run build` exits 0.
5. The mock /me validates against 1.24.0 for every persona. verify: `mock-live-me.test.ts` still validates each persona with the Ajv `/api/v1/me` schema, and a test fails if `positions`, `url` or `available` is removed from one fixture.
6. No assertion is weakened. verify: `git diff b8542c79 -- frontend/tests` shows no deleted or loosened `expect`, no `skip` or `todo`, no loosened Ajv option and no removed fixture. Assertions change only where the shape changed.
7. Code changes are only what the types force. verify: `git diff b8542c79 --stat -- frontend/src` is empty or lists only edits that clear a tsc error, and nothing under `src/` reads `positions`, `url` or `available` for new behaviour.
8. Negative case. verify: a /me body without `positions`, or a destination without `url` or `available`, fails the Ajv check in `mock-live-me.test.ts`.

## Out of scope
- Using `positions`, `url` or `available` in navigation, the shell, availability handling or any screen (F-67).
- Hand-editing `live-schema.d.ts` or the contract, regenerating them, and any backend change.
- Skipping or loosening tests or schema validation. Refactoring fixtures.

## Assumptions
- `url` mirrors the existing `django_url` or mock route, since 1.24.0 gives no value rule. Reason: the fixtures need only be valid, and F-67 owns the meaning.
- `available: true` by default. Reason: nothing in the sources says otherwise, and it keeps current test behaviour.
- `positions: []` where a persona has no matching role. Reason: the type allows an empty array.

## Conflicts with the boards
None. No screen, field, block or control is added, moved or removed.
