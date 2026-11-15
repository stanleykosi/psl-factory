VERDICT: PASS
COMMIT: 06b4c0e93bbc3083cea431c2f022c1e267486f24
REVIEWER: reviewer-ui
AUTHORITY: UI reviewer (round 1, design-fidelity gate)

## Summary
- All three desktop SCR-13 rules boards pass the fidelity tool at 1440: rules 93.4, finance 96.2, delivery 97.9, each at 100% coverage once exceptions apply.
- All three phone boards reach 100% coverage at 390, but their visual scores are 66.1, 78.9 and 83.7, below the 90 bar. In the side-by-sides the content matches card for card and row for row. The whole gap is the "← Setup" back link (and the RULES label), which sits under the frame's phone bar instead of inside it. D-08 and D-22 accept this until the frame slot (D-23) lands, so it does not block this round.
- Nothing scrolls sideways at 390 or 1440 on the rules, finance, delivery or reserved-tab pages, in the default, mobile, readonly or empty scenarios.
- `setup.css` uses only token variables (`--ink`, `--ink-muted`, `--surface`, `--rule-soft`, `--focus`, `--font-*`), with no hard-coded colours. Tables, buttons, inputs, banners and empty panels reuse the shared `psl-*` classes.

## Findings
None.

## Verified
None (round 1).

## Notes
- **How the gate was run.** I ran `fidelity.mjs` against the shared build at http://localhost:4111 with `--exceptions /Users/Hunchoo/psl-factory/delivery/features/F-11/fidelity-exceptions.json`. Each board used its own site-wide cookies:
  - desktop-rules and desktop-delivery: `psl_mock_persona=admin`, `psl_mock_setup=desktop`;
  - desktop-finance: `psl_mock_persona=finance_lead`, `psl_mock_setup=desktop`, because that board's bar reads "Ada Okafor · Finance Lead". My first run of this board as admin failed only on that persona text;
  - the three phone boards: `psl_mock_persona=admin`, `psl_mock_setup=mobile`.

  The output is in `round-1/fidelity-review/<board>-<width>/` (report.json, report.html, side-by-side.png, page and board images). Extra state screenshots are in `round-1/fidelity-review/states/`.

  | Board | Coverage raw (with exceptions) | Visual | Tool |
  |---|---|---|---|
  | SCR-13-desktop-rules 1440 | 77.6% (100%) | 93.4 | PASS |
  | SCR-13-desktop-finance-rules 1440 | 93.1% (100%) | 96.2 | PASS |
  | SCR-13-desktop-delivery-rules 1440 | 93.9% (100%) | 97.9 | PASS |
  | SCR-13-mobile-rules 390 | 14.3% (100%) | 66.1 | FAIL (visual, D-08/D-22) |
  | SCR-13-mobile-finance-rules 390 | 100% | 78.9 | FAIL (visual, D-08/D-22) |
  | SCR-13-mobile-delivery-rules 390 | 100% | 83.7 | FAIL (visual, D-08/D-22) |

- **The phone boards need a re-run.** Once the D-23 frame back-link slot reaches this branch, "← Setup" and "RULES" should move into the phone bar and all three phone boards should be re-run. Every content block is already in place, so I expect them to clear 90. On the phone, the tool's only extra items are the frame's Menu button and PSL FACTORY.
- **Desktop-rules data drift on the shared mock.** On the shared mock, someone had already saved "Who may assign an RFP to a PM" (CEO, v1 · since 14 Nov). The page therefore shows Rules 7, a 7-rule banner and "Save as version 2", where the board shows 8 and "Save as version 1". This is shared-mock state from another session, not a build difference: the `readonly` scenario shows the board's 8 rules and Not set. Even in this state the board scores 93.4. I did not reset the mock.
- **Approved deviations seen in the side-by-sides.** Each one is covered by the exceptions file, D-22 or spec assumptions:
  - Start work is absent from the bar (F-05).
  - The tabs are a nav of links (A-7).
  - Rule is a native select and Starts is a native date input (A-11).
  - Why and Proof start empty (A-14).
  - PMO Lead appears once (PMO-0-4).
  - AREA texts "Finance" and "Delivery", and the breadcrumb SETUP / RULES, are blue underlined links (A-8, which D-22 accepts).
  - The button reads "Set BU totals rules" where the board has "Set bu totals rules".
- **Taste, not blocking.**
  - On the reserved tabs (for example `/setup/roles`), the Roles and Rules count badges disappear, because those routes read no counts. The tab bar is then a little narrower than on Rules. That is consistent with the spec's no-request rule, but the bar visibly changes width between tabs.
  - On desktop finance, "Set management accounts rules" nearly fills its 220px button, leaving very little side padding. The board does the same.
  - On the phone, Finance list rows are about 1px shorter than on the board (40px against 41px). This is not visible at normal zoom.
- **Contrast.** The red NOT SET and HOLDS WORK tags, the amber "Not set" text, the banner text on its cream background and the blue info callout all use the shared tag and callout tokens already used on other screens. I found no new low-contrast pairing. The builder's axe runs report no violations.
- **Session.** I used no dev server of my own: the coordinator's DISK RULE applies, so I used the shared build on 4111. The headless browser I used for screenshots is closed.
