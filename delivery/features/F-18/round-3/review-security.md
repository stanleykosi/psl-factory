VERDICT: PASS
COMMIT: 9d0fc66882834dc35d0116738d46c0bb5f12da58
REVIEWER: reviewer-security
AUTHORITY: security reviewer

Diff 28c13dbc..9d0fc66 touches only rfp.css (phone spacing) and one FollowupCard.tsx condition. showNote now requires status drafted AND (canSend || canEdit), derived from server flags can_send/can_edit. The change only narrows when a note is shown. Send/Edit gating (lines 83-84, 166-173) is unchanged, so no new send path or exposure. No findings.
