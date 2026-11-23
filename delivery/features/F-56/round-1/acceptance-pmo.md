VERDICT: PASS
COMMIT: abf2482a0bbc656b975f1f1afda722df6cdf7941
REVIEWER: pmo-acceptance
AUTHORITY: pmo-acceptance

## Summary
- Delivery accepted for F-56 (FE-CONNECT-1, part a only) on head abf2482a. The gate passed (checks.md, attempt 1, no protected paths changed). Technical, security, UX, UI and QA all PASS on this same head.
- Scope matches readiness and spec: FactoryDesk deleted, the AppShell embed branch removed, and next.config.ts narrowed to /api/v1, six download routes and the mock-only reset. No backend file, no operation ID and no screen data changed. No operation IDs were in scope.
- No blocking finding exists. Four non-blocking findings are open (TECH-1-1, TECH-1-2, QA-1-1, QA-1-2), each with a named owner below.
- Two things differ from the spec and are accepted: criterion 11 (Django answers 302, not a JSON 401) and criterion 8 (`next start`, not `next dev`, so Reset demo was not run). Both rest on D-172 and are listed below.
- This PASS is delivery acceptance only. Product acceptance is not required (readiness). Merge and release keep their own authorities, and the design gate stays on the D-173 exception.

## Findings
- PMO-1-1 | non-blocking | low | pmo | Scope the technical and QA reviews left unproved (see Verified-scope table below) must be carried to the named owners and not read as proved. Evidence: review-qa.md "Not proved", build.md criterion 8.
- PMO-1-2 | non-blocking | low | pmo | The branch also carries a commit outside the spec's lanes: the `frontend/tests/assistant-dictation.test.ts` repair (path fix plus a holder object in place of the `this` alias). The coordinator requested it, it is a test-only change, and the technical review found no assertion relaxed. It was needed for the gate to pass. Record it in the merge note as a separate item. Other changed paths (architecture v8 package, decisions files, F-57 record, design/review.json) are the planning commits for D-172 and D-173, not feature code.

## Acceptance check
- Criteria 1 to 7 and 12: passing evidence on this head in `next-config.test.ts`, `shell-no-embed.test.tsx` and the full gate (153 files, 3636 tests, lint, typecheck, build). No existing shell test was edited (technical review). The build notes say the design check has no separate step in `checks.sh`; the design gate is the D-173 exception.
- Criterion 9: Next 404 for `/no-such-page`, `/accounts/login/` and `/static/x.js`, and Django not hit (build.md log check; review-qa.md).
- Criterion 10: a signed-out visit shows "You're signed out. Sign in" with no Django login widget and no JSON. `/api/v1/me` returns 401 JSON through the proxy (build.md, headless Chromium). QA saw the same, with Django behind a forwarder.
- Criterion 8 (with a gap): the mock frame draws on `/` and `/my-work` with no `psl-work-client` and no failed requests (build.md on a `next start` build; QA on port 3000). Reset demo was not exercised. The reset flag matrix is unit-tested and the code for it did not change.
- Criterion 11 (with a difference): the six routes reach Django and keep its checks. The unauthenticated answer is a 302 to `/accounts/login/`, not an API 401. Near misses and `not-a-uuid` stay in Next and never reach Django. Accepted, see TECH-1-1/QA-1-1.
- Task and operation coverage: FE-CONNECT-1 part a is the only task in scope. No operation IDs. Nothing outside scope landed (see PMO-1-2).
- Blocking findings: none raised, so none to verify. Accepted risks: the D-172 sign-in gap (SCR-17 absent until wave 1) and the D-173 design exception. D-172 and D-173 are recorded in `delivery/OVERNIGHT-DECISIONS.md` and `architecture/sources/decisions-2026-11-23.md`. The authority behind both is the design engineer, who also said "Yes, start wave 0".
- Docs and handoff: the spec requires none beyond build notes with the live-check commands, which build.md records.
- Parent package: FE-CONNECT-1 is part a only. F-57 holds part b (live types, live client, session handling, frame on live `/me`, role words). The task must not be marked complete from F-56 alone, and F-56 makes no claim that the live frame is right (it still reads the v7 `/me` shape, per D-172).

## Non-blocking follow-ups and where each is owned
| Item | What | Next owner |
|---|---|---|
| TECH-1-1 / QA-1-1 | An unauthenticated download gets Django's 302 to `/accounts/login/` (`@login_required`, `apps/agents/upload_views.py:57,118`), which lands on a Next 404 until SCR-17. Backend should answer download routes with an API-form 401. | Backend questions list: `delivery/connect/backend-questions.md` (raise as a new question). F-57 handles how the frontend treats the result; wave 1 (SCR-17) supplies the sign-in page the person should land on. |
| TECH-1-2 | `next-config.test.ts` should assert each exact download destination (for example `${API}/work/:work/invoice-proof/:proof/`). | F-57 (the next frontend feature to touch `next.config.ts` tests), or any later change to the rewrite list. Hardening only. |
| QA-1-2 | A request ending in `/` gets a Next 308 to the slash-less path before the rewrite; the proxied request still reaches Django with the slash. Works. Only `curl` without `-L` looks different from the spec's example. | No fix needed. Note for F-57 and wave 1 when writing live download checks: use `-L` or the slash-less path. |

## Scope QA left unproved and where it is owned next
| Not proved | Why | Next owner |
|---|---|---|
| A single Next-to-Django hop through `next start` | QA's existing build was bound to `http://127.0.0.1:4010`, so QA used a stub for the forward check. The builder did run a real hop (build.md criteria 10 and 11, build with `API_ORIGIN=http://127.0.0.1:8000`, `next start -p 4960`) and it passed. The two together cover it, but QA did not repeat it. | F-57 live check against the live API (its first end-to-end run). |
| Signed-in wrong-user and wrong-tenant downloads | No sign-in page exists (D-172), and no session was used. Django's per-record checks are code-reviewed by security (all six views have `@login_required`, `@require_safe` and a per-record access check) but not exercised through the proxy. | Wave 1 (SCR-17 gives a real sign-in), with F-57 session handling. Until then the proxy adds no authority and Django's checks stand alone. |
| Reset demo | A dev-only route. Neither the builder (dev-server lock, so `next start`) nor QA exercised it. The flag matrix is unit-tested and the code is unchanged. | The next mock-mode `npm run dev` run, in F-57's acceptance run. |

## Verified
None (round 1, no fixes to retest).
