VERDICT: PASS
COMMIT: df180ca0716d9a70e19bc82f5df57cce37e99aeb
REVIEWER: reviewer-ui
AUTHORITY: UI design reviewer (fidelity gate)

## Summary
- UI-1-1 is fixed. On both done boards the next-step card now sits on `--action-tint` with `--action-ink` text and Chidi's thumbs-up done pose (`/agents/chidi-done.png`). It matches the boards at 1440 and 390. Done scores rose to 95.2 (desktop) and 94.9 (phone).
- UI-1-2 is fixed. On phone stale, the agent note now sits inside the current version card below a 2px ink rule, Amount uses the mono figure, and the changed/unchanged marks are small and muted. The two stacked panels stay, as D-56 waived.
- I re-ran the gate on all 10 SCR-03 boards against 4631 (mock 4632). For done and stale I froze fresh pages through the real UI and served them on 4633. All 10 boards have 100% coverage after exceptions. Nine scores match build.md exactly. Phone stale is 78.8 against build.md's 78.9 (sub-point font/time noise). The same five boards are under 90, and all five carry D-56 waivers.
- The new hidden h1s (5xx and 401) and the `role="status"` line add no visible content: `.decide-sr` is clipped to 1x1. The focused done heading shows no ring after a mouse click. After a keyboard Enter it shows the standard 2px `--focus` ring, which is correct.
- Tokens only. The round-2 diff adds no hard-coded colours or inline styles, and nothing overflows at 390.

## Findings
- UI-2-1 | non-blocking | low | frontend | On phone done, "Paid is tracked separately by Finance" now reads twice. It is the last sentence of the next-step card, and it is also the separate line under the card. The SCR-03-mobile-done card text ends at "...once the delivery receipt comes back." and the Paid sentence appears only as the line below. Round 2 removed the same duplication on desktop only (DecideStates.tsx DoneView). Expected: on phones, drop the Paid sentence from the card text and keep the line. See round-2/fidelity-review/SCR-03-mobile-done-390/side-by-side.png.

## Verified
- UI-1-1 | verified | Frozen done-1440 and done-390 (driven by Approve v2 on W-1901) both reference `chidi-done.png`. In the side-by-sides the card is the blue agent surface with the thumbs-up pose, the same as the boards (decide.css `.psl-callout.decide-next { background: var(--action-tint); color: var(--action-ink); }`). The phone text is `--action-ink` on `--action-tint`, a pair the boards use, so the earlier blue-on-green pairing is gone. Desktop done 95.2 PASS, phone done 94.9 PASS.
- UI-1-2 | verified | In frozen stale-390 the current card ends with the Chidi note inside it, separated by a 2px ink top rule. The Amount "₦4,250,000.00" is in mono. "unchanged" and "changed" are 12px muted, not bold red. Remaining differences are the replaced panel's full rows, the Basis row and the "Changed since Invoice v2" line, all of which are inside the D-56 waiver and Conflicts 16. Score 78.8 (waived).

## Fidelity gate (round-2/fidelity-review/<board>-<width>/report.json + side-by-side.png)
| board | width | coverage | with exceptions | visual | tool | missing/moved/extra |
|---|---|---|---|---|---|---|
| SCR-03-desktop | 1440 | 91.3 | 100 | 91.1 | PASS | 4/1/7 |
| SCR-03-mobile | 390 | 70 | 100 | 85.0 | fail, D-56 waiver | 6/5/9 |
| SCR-03-desktop-done | 1440 | 96.4 | 100 | 95.2 | PASS | 1/1/3 |
| SCR-03-mobile-done | 390 | 89.5 | 100 | 94.9 | PASS | 2/0/5 |
| SCR-03-desktop-stale | 1440 | 82.1 | 100 | 88.2 | fail, D-56 waiver | 5/6/7 |
| SCR-03-mobile-stale | 390 | 58.3 | 100 | 78.8 | fail, D-56 waiver | 5/1/8 |
| SCR-03-desktop-not-yours | 1440 | 90.9 | 100 | 91.4 | PASS | 2/1/9 |
| SCR-03-mobile-not-yours | 390 | 66.7 | 100 | 84.7 | fail, D-56 waiver | 6/2/10 |
| SCR-03-desktop-own | 1440 | 81.3 | 100 | 91.6 | PASS | 3/2/9 |
| SCR-03-mobile-own | 390 | 50 | 100 | 77.8 | fail, D-56 waiver | 2/1/11 |

Every missing element is covered by an entry in `fidelity-exceptions.json`. The five boards under 90 have the same gaps and causes as in round 1 (see round-1/review-ui.md Notes). Round 2 changed none of those boards except phone stale, where the change moves the page closer to the board.

## Carried forward (impact assessment)
- The round-2 diff covers DecideStates.tsx, DecisionContent.tsx, DecideView.tsx, five lines of decide.css, one new PNG and tests. It does not touch the default, not-yours or own layouts. Their scores are identical to round 1 (91.1/85.0, 91.4/84.7, 91.6/77.8), so my round-1 reading of those boards stands.
- The new phone-stale CSS is scoped to `.decide-compare__new` inside the phone media query. Desktop stale is unchanged at 88.2.
- The heading focus uses `tabIndex=-1` and relies on the UA `:focus-visible` behaviour, so mouse users see no ring and keyboard users see the `--focus` ring. No layout shift.

## Notes
- The built done card has a bold "Next step." lead-in that the boards do not draw. It is small and reads well, so I treat it as taste.
- The phone and desktop done strips show RECEIPT "Unknown" on the amber surface, where the boards draw "—". This comes from the fixture's `presentation.facts` and follows the "unknown is not zero" rule. It is unchanged from round 1 and is not a round-2 regression.
- The open round-1 items still stand. The `fidelity-exceptions.json` entries still read "builder proposal, pending design engineer" and should record the D-55/D-56 sign-off before merge (owner: product). The phone default waiver wording is narrower than its actual gap. The done eyebrow time (live `decided_at`) differs from the fixture's APPROVED 10:47. DE-5 ("+ Start" in the phone bar) is a shell matter.
- Method: `round-1/fidelity/drive-states.mjs` and `serve-frozen.mjs`, copied to a scratch folder and pointed at 4631, 4632 and 4633. The tool ran with `--cookies psl_mock_persona=finance_lead --wait-ms 500` and the feature's exceptions. The mock was reset after each run. The 4633 server is stopped. The 4631 and 4632 servers were left running.
