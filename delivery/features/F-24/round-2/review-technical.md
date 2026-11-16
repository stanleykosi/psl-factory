VERDICT: PASS
COMMIT: 0f94b4b21e40889bb0300b3cf6891bab76829677
REVIEWER: reviewer-technical
AUTHORITY: delivery technical review

## Summary
- TECH-1-1 and TECH-1-2 are fixed as asked; nothing is resent automatically.
- The shared phone bar change is additive: a note without `onNote` still renders as the same span, with only a one-line ellipsis, a left gap, and a back link that stays on one line.
- The new Start work `onConflict` is optional, passed through drawer, form and hook, and called only on a 409 that is not `idempotency_key_reused`. Behaviour without it is unchanged.
- Read-only review of the diff 10c7accc..0f94b4b2; no servers or tests run.

## Findings
None.

## Verified
- TECH-1-1 | verified | `useSend.ts` now compares the number of person messages after the re-read with `personCount` (the count shown before the send), so identical earlier text no longer counts as delivered. The uncertain path still never resends and still waits for "Try again". Round 2 adds a same-text lost-send test.
- TECH-1-2 | verified | `assistant.mjs` `draftStart` now checks both the 201 and the 409 replies against the v7 E-WORK-START response schema and answers 500 `mock_invalid_reply` on mismatch.
- TECH-1-3 | verified | Left as is, as agreed (non-blocking).

## Notes
- Shared shell: `usePhoneBack` adds `onNote` to the effect dependencies. The only caller that passes it is the assistant home, with the stable `showList` callback, so there is no re-set loop. The other nine callers pass no `onNote` (undefined stays stable). The `.psl-phonebar a[aria-label^="Back to"]` rule (nowrap, flex none) applies to every page, but back labels are short single words and the note now truncates instead, so no overflow is expected.
