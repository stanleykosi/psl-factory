VERDICT: PASS
COMMIT: a3b587107fba754884bfd399d9a4dc25d32c7ab1
REVIEWER: reviewer-ux
AUTHORITY: delegated UX review

## Re-confirmed on the synced head
The branch since 31f0d25e only merged origin/dlv-00-delivery-setup (F-19 Clients). The diff stat over workspace, work-item, shell and the work fixtures shows one change: frontend/src/shell/destinations.ts, +2 lines. It maps /clients paths to the Projects destination in destinationForPath. The weekly journey does not use /clients, so nothing it touches changed. Workspace, work-item and the work fixtures are unchanged. No findings.

## Earlier review (at 31f0d25e)


## Verified
- UX-1-1 | verified | The hint no longer promises that saved cites are kept. It now tells the PM what to do on this page. Read from the diff and fixture, not walked in a browser. The fixture has exactly two `help` strings, and each is on the first records field of a W-2201 step (`status_cites` in the first, and the matching first field in the second). The per-field helps are gone. The shared frame is unchanged.
- UX-2-1 | verified | The wording is exactly the sentence I asked for: "Saved records are not shown here. Choose at least one record for this part before you send." It makes no claim about what the server keeps, so it no longer contradicts the Send 422. It appears once per step, not on every field. The hint test now asserts the new sentence once, on the Save draft form. The records-field `value` (prefill) question stays with the coordinator as the real fix, after which the hint can go.

## Findings
none
