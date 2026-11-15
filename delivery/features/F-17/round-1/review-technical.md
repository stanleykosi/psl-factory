VERDICT: PASS
COMMIT: 1432023f985798659f2cc4342c3a745936d30324
REVIEWER: reviewer-technical
AUTHORITY: technical reviewer (lead)

## Summary
- The step write holds the spec. It has one key per attempt, a synchronous in-flight guard and no timers or effects that send. Keys renew only after done, 409 or 422, or when a form opens. The shared client carries CSRF, and 422 field names are kept.
- Outcomes behave as written. Queued and done reload once. effect_uncertain turns off every step and shows reconcile only when the reloaded item allows it. 409 re-bases the revision and keeps the inputs. 403 reloads, and a 403 or 404 on the re-read shows NoAccessState. A failed `sends` step is locked.
- Unknown values never become zero (null from the formatters gives "Unknown", a blank money field is sent as `unknown: true`). Restricted sections, items, cells and fields return early with no data. Links go only through `refPath` and `isAppPath`, and `crumb.value` is plain text.
- WorkItemView takes the newer of the two reads. Tests cover the negative cases (401, 403, 403 then 403, 404, 500 on a `sends` step, the 60 second no-retry check, StrictMode).
- Layout fidelity is out of scope here (FID-1-1 and D-62). The findings below are non-blocking.

## Findings
- TECH-1-1 | non-blocking | low | frontend | `useWorkspacePage` keeps `fresh`, `lost` and `refreshFailed` in state with no reset when `id` changes (frontend/src/features/workspace/usePageReload.ts:25-27). If Next ever reuses the WorkItemView instance across ids, a `lost` set on one item would show NoAccessState for the next. Next normally remounts a changed dynamic segment, but cites now link between work items. Reset the state on `id` or key the hook by id.
- TECH-1-2 | non-blocking | low | frontend | When the 409 re-read fails, the notice reads "Showing version unknown" (frontend/src/features/workspace/useWorkspaceStep.ts:41, :127). The controls are off by then because `refreshFailed` is set, so the page should say it could not reload, not name a version.
- TECH-1-3 | non-blocking | low | frontend | A facts item whose `value` is an empty string draws a blank `dd`, not Unknown (frontend/src/features/workspace/Sections.tsx:~150, `item.value !== undefined`). INV-UNKNOWN says missing is never blank. Treat `''` and `null` as unknown.
- TECH-1-4 | non-blocking | low | frontend | The manual "Try again" for a non-`sends` step reuses the key but sends the reloaded `expected_revision` (useWorkspaceStep.ts:97). If the first attempt did land, the retry is a 409 on the real backend, since the idempotency promise is unbuilt. This is in the spec and the build records it. It needs a backend answer before a real-API cutover. No change now.

## Verified
None (round 1).
