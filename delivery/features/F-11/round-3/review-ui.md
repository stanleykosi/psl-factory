VERDICT: PASS
COMMIT: 604e1b0a0f8fb3ac2cee49124f70370b1343e6de
REVIEWER: reviewer-ui
AUTHORITY: UI reviewer (round 3, design-fidelity gate)

## Summary
- All six SCR-13 boards PASS the design-fidelity gate at head 604e1b0 against the shared build on 4111 (mock 4112), at 100% coverage with the approved exceptions. Desktop: rules 93.4, finance 96.2, delivery 97.9. Phone: rules 99.8, finance 99.1, delivery 99.7 (round 2 was 66.0, 78.9 and 83.7).
- FID-2-1 is fixed. "← Setup" now sits in the frame phone bar where the boards draw it, and the Menu button and PSL FACTORY are gone on these three views. The page-local link under the bar has been removed.
- The "RULES" note matches the boards exactly: IBM Plex Mono 12px, white on the ink bar, at the right of the bar, on Finance and Delivery only. The Rules view has no note, as on its board.
- The phone bar on other pages is unchanged. /my-work, /setup/roles and /setup/staff still show Menu and PSL FACTORY with no note. After going back from Finance to /setup/roles, the note is cleared.
- Nothing overflows sideways at 390 on any of the three views.

## Findings
None.

## Verified
- FID-2-1 | verified | I re-ran fidelity.mjs on 4111 with `fidelity-exceptions.json`, which includes the D-33 "← Setup" exception. Phone visual is 99.8 / 99.1 / 99.7 and every board PASSES. The only remaining phone differences are:
  - the link the tool reads as "Back to Setup" (the frame's accessible name, D-33);
  - "RULES", which the tool marks as moved by a few pixels.
  Side-by-sides: `round-3/fidelity-review/SCR-13-mobile-{rules,finance-rules,delivery-rules}-390/side-by-side.png`. A live DOM check at 390 found the bar holds `A[aria-label="Back to Setup"]` with text "← Setup" plus `span.shell-phonenote` "RULES" (finance and delivery), and no Menu.
- TECH-2-1 | not in UI lens | This is panel and callout logic with no new visual. The callout is the same OutcomeNotice I verified in round 2.
- SEC-2-1 | not in UI lens | This is a test-only change.

## Notes
- **How the gate was run.** I ran `fidelity.mjs` from /Users/Hunchoo/software-factory/packages/design/fidelity/ against http://localhost:4111 with `--exceptions delivery/features/F-11/fidelity-exceptions.json`. The 4111 build is from the f-11 worktree at 604e1b0, and its BUILD_ID is dated after the commit. The cookies were the same as round 2:
  - desktop-rules and desktop-delivery: `psl_mock_persona=admin,psl_mock_setup=desktop`;
  - desktop-finance: `psl_mock_persona=finance_lead,psl_mock_setup=desktop`;
  - the phone boards: `psl_mock_persona=admin,psl_mock_setup=mobile`.

  My scores match the builder's round-3 results on 4601. The output folder `round-3/fidelity-review/` holds only report.json and side-by-side.png per board.

  | Board | Coverage raw (with exceptions) | Visual | Tool |
  |---|---|---|---|
  | SCR-13-desktop-rules 1440 | 77.6% (100%) | 93.4 | PASS |
  | SCR-13-desktop-finance-rules 1440 | 93.1% (100%) | 96.2 | PASS |
  | SCR-13-desktop-delivery-rules 1440 | 93.9% (100%) | 97.9 | PASS |
  | SCR-13-mobile-rules 390 | 7.1% (100%) | 99.8 | PASS |
  | SCR-13-mobile-finance-rules 390 | 87.5% (100%) | 99.1 | PASS |
  | SCR-13-mobile-delivery-rules 390 | 66.7% (100%) | 99.7 | PASS |

- **The pass relies on a provisional exception.** The phone boards reach 100% coverage only because of the D-33 exception: the board's link name "← Setup" against the frame's "Back to Setup". It is provisional and approved by the coordinator. If D-33 is reverted, the phone boards fail coverage (92.9% / 87.5% / 66.7%), although nothing visible changes.
- **The shell change is small and uses tokens.** `.shell-phonenote` sets only `font-family: var(--font-mono)` and 12px, and inherits `--on-strong` from `.psl-phonebar`. The 12px size matches the existing `.psl-crumb` mono size. The `note` field is optional, so pages that never pass it render as before.
- **Approved deviation still visible on Rules at 390.** The area words "Finance" and "Delivery" on the phone cards are blue underlined links, where the board draws plain brown text. Spec assumption A-8 approves this, and it is unchanged since round 1.
- **Session.** I used the shared 4111/4112 servers only. I started and stopped no servers, and ran headless Chromium (session F-11-ui), now closed. Scratch screenshots are deleted.
