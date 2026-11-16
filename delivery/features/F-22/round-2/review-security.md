VERDICT: PASS
COMMIT: 0cc0a73b6ae0982016c6176c88972adf6247a6bc
REVIEWER: reviewer-security
AUTHORITY: delivery security review

## Summary
- SEC-1-1 is fixed. The 404 and 403 tests now wait for the real no-access state before checking that no title, client or id is shown. A real 401 test checks the signed-out callout and `next=%2Fwork%2FW-2299`.
- SEC-1-2 is fixed. Request URLs are collected in a list that is never reset, and the hostname check runs in `afterEach`, so it covers the whole run (Playwright runs with `workers: 1`).
- SEC-1-3 stays a recorded follow-up: it is older shared code in a read-only lane.
- The round-2 code diff (6d857c31..7202d804) changes only layout and naming: the Next panel's classes, the `aside` name and the button colour. It changes nothing about data, access, sending or reconcile. No new findings.

## Findings
None.

## Verified
- SEC-1-1 | verified | frontend/tests/weekly-returned-received.test.tsx:256-277. The 404 and 403 tests use `findByText` on the NoAccessState sentence (src/features/work-item/WorkItemStates.tsx:53, "...not even its name or amount."), then check that the body has no "Lagoon Health", "Weekly client report", "W-2299" or "WCR-0216". The 401 test waits for "You're signed out." (src/shell/FrameStates.tsx:23), checks the Sign in link is `/accounts/login/?next=%2Fwork%2FW-2299` and that nothing about the item leaks. A further 403-on-step test waits for "You can't take that step." (useWorkspaceStep.ts:43). Each test now waits for the state it names, so none can pass before the page loads.
- SEC-1-2 | verified | frontend/e2e/weekly-returned-received.spec.ts:13-28. `everything` is a module-level list that is never cleared. Every page request goes into it, and `test.afterEach` checks every URL's hostname is localhost or 127.0.0.1. playwright.config.ts:9-10 sets `fullyParallel: false, workers: 1`, so one list sees every test in the file. The old single-page test is removed. Not re-run by me (read-only review); build.md reports 79 e2e passed.
- SEC-1-3 | accepted | Recorded follow-up per the coordinator. The "never invoiced twice" sentence in frontend/src/features/response/ReconcilePanel.tsx:136 is older shared code in a read-only lane; this round leaves it unchanged. Impact: wrong-domain copy and a no-duplicate wording on the W-2212 mock page only. Nothing is sent and the behaviour stays reconcile-only.

## Notes
- Carried forward from round 1 by impact assessment. Sections.tsx gains only a `ws-section--untitled` class, and Workspace.tsx changes only class names and `aria-label`/`aria-labelledby`. Steps still come only from `workspace.steps`, the reconcile lock from `item.reconcile`/`allowed_actions`, and tags and status from the data. The round-1 conclusions on delivery truthfulness, no resend, access and secrets still hold.
- No new dependency, fixture or mock-handler change in this round. No secrets in the diff (the fidelity reports contain only the mock persona cookie `psl_mock_persona=pm`).
- Head moved 7202d804 -> 0cc0a73b. Checked in /Users/Hunchoo/psl-factory-worktrees/f-22: `git diff --stat 7202d804 0cc0a73b -- frontend` is empty. `git diff --name-only` lists only `delivery/**` files: the F-22 exceptions sign-off (D-99), round records and review files, the F-23/F-24 specs, OVERNIGHT-DECISIONS.md and events.jsonl. A grep of the added lines finds no secrets. No code changed since 7202d804, so the verdict and the verifications above stand for 0cc0a73b.
