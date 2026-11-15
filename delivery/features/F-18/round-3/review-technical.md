VERDICT: PASS
COMMIT: 9d0fc66882834dc35d0116738d46c0bb5f12da58
REVIEWER: reviewer-technical
AUTHORITY: technical reviewer (lead)

# Technical review, F-18 round 3

Scope: `git diff 28c13dbc..9d0fc66`. It changes two files, `rfp.css` and `FollowupCard.tsx`.

- `FollowupCard.tsx`: `showNote={status === 'drafted' && (canSend || canEdit)}`. `canSend` and `canEdit` are defined above it (lines 83-84), so the reference is valid. The change only hides the "It goes only if you send it." note from viewers who can neither send nor edit. That is a display change. It touches no payload, API or permission rule. Permissions are still enforced server-side through `can_send` and `can_edit`.
- `rfp.css`: the added rules are phone-only, inside the existing media block, and scoped under `.rfp-recorded`. They set spacing and heading size only. They cannot reach other screens.
- Contract, permissions and tests: no problems. The gate evidence (round-3/build.md, `playwright test rfp` 30 passed) covers the change.

Earlier non-blocking items carry forward from round-2/review-technical.md unchanged.
