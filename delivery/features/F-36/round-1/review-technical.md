VERDICT: PASS
REVIEWER: reviewer-technical
COMMIT: 264b349260dbbd734eaadcb5228781f83cccccb0
AUTHORITY: delivery technical review

## Summary
- Assign panel is gated on the item's own `assign`. No `assign` on the first read means `router.replace` to `/work/<id>`. Candidates come only from `assign.candidates`. Nothing is read from `/me`. Nothing is chosen ahead, and a chosen person who drops off a re-read is cleared with a sentence.
- Success words come only after the item re-read (`useWorkspaceAssign` sets `done` after `page.reload()`) and the list re-read (`assigned()` awaits `refresh(true)`). 409, 422, 5xx, network and uncertain paths never resend. The `writing` ref guards double presses. `expected_revision` comes from the item, with a `revision` fallback after a stale read.
- F-30/F-31 reuse is additive: new optional AssignForm props default to the old behaviour, and the old call sites are unchanged. The one behaviour shift is that the F-30 "Owner set" notice now appears after the re-read instead of before. That is the stricter order and is acceptable.
- Mock overlay G-24-1/2/3 and the `pmo_lead` persona are mock-only and read through `proposals.ts`. The body stays the typed one when the overlay is absent. ProofField reuse is sound.
- The `fileSize` fix ("Size unknown" for a non-finite size) is a safe, minimal shared change. The e2e W-1099 not-open case and the `waitFor` on the rows in the rfp-assign test are legitimate: no assertion was loosened and no timeout was raised.

## Findings
None.
