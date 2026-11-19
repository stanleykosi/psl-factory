VERDICT: PASS
REVIEWER: reviewer-technical
COMMIT: ee9dc46dca9ff40d39148cc4ba1f76572bb35aa7
AUTHORITY: delivery technical review

## Summary
- TECH-1-1 fixed: stepsOf drops a step reference whose words equal a restricted source label or reference; the restricted source itself draws only the lock chip.
- New tests cover the spec cases; the label test fails with the fix removed (checked in a temp copy).
- All 41 fidelity exceptions carry a Conflicts number; the restricted-label wording is corrected.
- Later dlv-00 merges did not touch assistant source, tests, fixtures or mock.

## Findings
- TECH-2-1 | non-blocking | low | frontend | `hidden` in model.ts:19 compares only `refWords` (label, else reference). A step with a different label but a restricted `reference` string would still draw its label; harmless today (label only, fixture has none). Better fix is the contract marking step references `restricted`; raise with integration later.

## Verified
- TECH-1-1 | verified | Read model.ts:17-25, Thread.tsx stepRecord, sourcesOf (restricted keeps nothing), SourceTag. Paths that could draw the label: steps (now dropped), sources (lock only), chips (none), reason text (fixture is plain text), phone/desktop share Thread. Mutation run (`!hidden.has(words)` replaced by `true`) fails the CV-2404 body-text test at 1440/390.
- TECH-1-2 | verified | Added tests: CV-2404 label absent at 1440 and 390, cannot_reason markup literal with no img/b element, finance_lead and unknown id see not-found with nothing of the refusal. 59 passed on head. Only the label test fails without the fix; the others are regression guards.
- TECH-1-3 | verified | Scripted check of fidelity-exceptions.json: 41 entries, every reason contains "Conflicts"; restricted-label entry now says it is hidden in the step (an uncommitted edit in the main repo, coordinator to commit).
- TECH-1-4 | verified | Test asserts the reason's `.closest('.cmp-chat__cannot')` is itself and the text line is not inside one.
- Merges after d28b8b98 | verified | `git diff d28b8b98 HEAD --name-only` has no path under src/features/assistant, tests/assistant, mock/fixtures/assistant.
