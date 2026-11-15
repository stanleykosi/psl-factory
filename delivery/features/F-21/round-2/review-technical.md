VERDICT: PASS
COMMIT: 798c17f8b0b30f6aabf94dc0ff621a901b6df7e4
REVIEWER: reviewer-technical
AUTHORITY: delegated technical review

## Findings
- TECH-2-1 | non-blocking | low | backend/coordinator | The omitted-cites behaviour is safe on the frontend. The frame sends no `*_cites` key and no empty list when untouched, and the new test pins both. The hint "saved cites stay" is a server claim (omitted = keep) that the backend must confirm. Send on a saved draft without re-picking cites still returns 422 until `records` fields can prefill. This is the builder's own contract question for the coordinator, not a blocker.
- TECH-2-2 | non-blocking | low | builder | `data-form-open` is set only while a `ws:` form is open, and the form renders in the aside outside the Decide panel (Workspace.tsx:324). So `display:none` cannot hide the form. The form has its own submit and close, and a reconcile step uses the same `ws:` path, so no action or reconcile path is lost. Closing re-shows the bar, and the focus-return runs in rAF after the state change. The rule applies only in the phone media block. The bar's own "confirm first" hint is not shown while the form is open, which is acceptable.

Checked: the fixture-only changes (W-2201..2204) and the three new tests. No test weakened or skipped. No backend or contract change. Scope is within the lane.
