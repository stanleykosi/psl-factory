VERDICT: PASS
COMMIT: edc476370a1b20444d9807811a9d7b0a6ed2f503
REVIEWER: reviewer-ui
AUTHORITY: UI reviewer (round 2, design-fidelity gate)

## Summary
- The fidelity gate gives the same scores as round 1. The three desktop boards PASS at 1440: rules 93.4, finance 96.2 and delivery 97.9, each at 100% coverage once the approved exceptions apply. The three phone boards reach 100% coverage at 390 but score 66.0, 78.9 and 83.7 visually. As in round 1, the cause is the "← Setup" back link sitting under the frame bar. D-08, D-22 and D-23 accept this, and the frame slot has not reached this branch yet.
- The new page-level callout (QA-1-1) uses the design system's problem callout with no changes. It matches the inline callout on the SCR-13 validation board: #FBE3D9 background, #9A2F10 text, 10px 12px padding, 14px text, 10px gap and an 18px warning icon. It is the same `OutcomeNotice` component the panel already uses, so it adds no new CSS.
- The callout lines up with the "not set" banner above it, at the same x and width at both 1440 and 800, with 20px above and below, matching the rest of the page. It takes focus and does not scroll sideways. Its wording follows the STATES error pattern of saying that nothing was changed ("Nothing you entered was saved.").
- At phone width the page is read-only (D-15), so the callout never shows there. Rules and Finance at 390 have no sideways scroll.

## Findings
None.

## Verified
- QA-1-1 | verified | Shared build on 4111 (BUILD_ID dated after the head commit). I loaded the page as editable, set `psl_mock_setup=readonly` and saved, on Rules as admin and on Finance as finance_lead ("Set BU totals rules"), at 1440 and 800. On every run the panel closed and a red `role="alert"` callout appeared between the banner and the list with the exact withdrawn text, and it had focus. Screenshots: `round-2/fidelity-review/states/callout-{rules,finance}-{1440,800}.png`.
- QA-1-2 | not in UI lens | This is a mock evidence-id reset with no visual change.

## Notes
- **How the gate was run.** I ran `fidelity.mjs` from software-factory branch `design-fidelity-check` against http://localhost:4111 with `--exceptions F-11/fidelity-exceptions.json`. The cookies were the same as in round 1:
  - desktop-rules and desktop-delivery: admin + desktop;
  - desktop-finance: finance_lead + desktop;
  - the phone boards: admin + mobile.

  I kept only report.json, report.html, side-by-side.png and the log in `round-2/fidelity-review/`. The page, board and diff PNGs were pruned to keep the folder small, so images linked from report.html may be missing; side-by-side.png has the comparison.

  | Board | Coverage raw (with exceptions) | Visual | Tool |
  |---|---|---|---|
  | SCR-13-desktop-rules 1440 | 77.6% (100%) | 93.4 | PASS |
  | SCR-13-desktop-finance-rules 1440 | 93.1% (100%) | 96.2 | PASS |
  | SCR-13-desktop-delivery-rules 1440 | 93.9% (100%) | 97.9 | PASS |
  | SCR-13-mobile-rules 390 | 14.3% (100%) | 66.0 | FAIL (visual, D-08/D-22/D-23) |
  | SCR-13-mobile-finance-rules 390 | 100% | 78.9 | FAIL (visual, D-08/D-22/D-23) |
  | SCR-13-mobile-delivery-rules 390 | 100% | 83.7 | FAIL (visual, D-08/D-22/D-23) |

- **Phone boards still need a re-run once D-23 lands.** The frame back-link slot is not yet on origin/main or on this branch. Once it is, move "← Setup" into the slot and re-score the phone boards.
- **Focus ring.** The callout is focused from code, so `:focus-visible` does not match and no ring is drawn. This matches the panel's existing notice (`.setup-notice` in setup.css) and is what the boards do for alerts.
- **Taste, not blocking.** At 1440 the callout fits on one line and is 41px tall, the same height as the banner, so the two stack neatly. At 800 it wraps to two lines.
- **Contrast.** #9A2F10 on #FBE3D9 is about 6.2:1, which passes AA.
- **Session.** I started no server of my own; I used the shared build on 4111 and mock on 4112. The 403 saves did not change the mock's state. The headless browser is closed and the scratch files are deleted.
