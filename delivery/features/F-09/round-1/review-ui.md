VERDICT: CHANGES
COMMIT: 4efaee8910bfe52304b9f253e66d96689f03862b
REVIEWER: reviewer-ui
AUTHORITY: UI design reviewer (design-fidelity gate)

## Summary
- I re-ran the gate against the shared build at http://localhost:4911 (mock 4912), resetting the mock before each board. All four SCR-16 desktop boards pass (95.4, 96.5, 95.1, 92.7). Phone success passes (95.0). Phone default (80.7), validation (73.2) and SOW signed (89.0) fail the 90 visual rule.
- The phone default and validation failures come from the D-32 conflict, which is held for the design engineer: the spec keeps "When they responded" and the Note, and those boards don't draw them. The rows themselves line up once the fields are allowed for.
- One blocking issue is outside D-32. On the phone, the reference (SOW-0207 / REL-0077) sits beside the h1. Both the spec (section 6) and the boards put it at the right of the back-link bar. It is dark text on the page where the boards show white text in the bar.
- The code uses tokens throughout: response.css has no hard-coded colours, and nothing overflows at 390 (e2e scrollWidth check). F-09's reconcile panel and entry link on SCR-02 line up with the boards. The rest of SCR-02 is F-03's page and is reported only.
- None of the exception requests is approved. I judge all of them justified (see Notes).

## Findings
- UI-1-1 | blocking | medium | frontend | Phone reference placement differs from the spec and the boards. Spec section 6 says sow_signature shows "← SOW … with `context.document.reference` on the right" of the back bar. SCR-16-mobile-sow-signed and SCR-16-mobile-success draw "SOW-0207" / "REL-0077" at the right of the dark bar in white mono (board box x316 y21). The page puts it beside the h1 in ink colour (page box y75/y78, "looks": #FFFFFF on the board, #1F2427 on the page; fidelity-review/SCR-16-mobile-sow-signed-390, SCR-16-mobile-success-390). This is part of the 1-point shortfall on sow-signed (89.0). The spec does not record it as approved. Expected: move the reference into the bar's right slot. F-11 round 3 adds an optional right-side `note` to the phone bar (D-33), but that is not on the base yet. Either adopt it once F-11 merges, or get the design engineer to approve the interim placement as an exception.

## Verified
- None (round 1).

## Notes
- **Gate re-run** (reports and side-by-sides in `round-1/fidelity-review/<board>-<width>/`):

  | Board | Width | Visual | Coverage with requests | Result |
  |---|---|---|---|---|
  | SCR-16-desktop | 1440 | 95.4 | 100 | PASS |
  | SCR-16-desktop-validation | 1440 | 96.5 | 100 | PASS |
  | SCR-16-desktop-success | 1440 | 95.1 | 100 | PASS |
  | SCR-16-desktop-sow-signed | 1440 | 92.7 | 100 | PASS |
  | SCR-16-mobile | 390 | 80.7 | 100 | FAIL (D-32) |
  | SCR-16-mobile-validation | 390 | 73.2 | 100 | FAIL (D-32) |
  | SCR-16-mobile-success | 390 | 95.0 | 100 | PASS |
  | SCR-16-mobile-sow-signed | 390 | 89.0 | 100 | FAIL (Note + attestation, D-32 class; reference, UI-1-1) |
  | SCR-02-desktop-awaiting-reconciliation | 1440 | 58.9 | 100 | FAIL (F-03's page, report only) |
  | SCR-02-mobile-awaiting-reconciliation | 390 | 59.1 | 100 | FAIL (F-03's page, report only) |
  | SCR-02-desktop-waiting | 1440 | 51.0 | 100 | FAIL (F-03's page, report only) |
  | SCR-02-mobile-waiting | 390 | 52.7 | 100 | FAIL (F-03's page, report only) |

  The first SCR-02-mobile-waiting run came back at 94.7% coverage. W-1601 was already recorded ("READY TO CONTINUE", no entry link) because another agent wrote to the shared mock between the reset and the page load. A clean re-run shows the "Record the client's response" link and 100%. That run is the one stored. This is not a defect.
- **D-32 (held for the design engineer; reported, not judged):** SCR-16-mobile and -validation draw no "When they responded" and no Note, which pushes every later row down about 110–170px. SCR-16-mobile also omits the "What they did" and "Proof" labels that -validation draws; keeping them in both states is consistent and I accept it. On SCR-16-mobile-sow-signed, Document through "What happens next" align to the pixel. The Note and attestation below them, which the spec requires (section 5, Assumption 529), push the pinned Record bar to y840 in the full-page capture. The attestation on the SOW boards is the same class of conflict and should be settled with D-32.
- **Desktop SOW layout (taste, non-blocking):** to keep the board's rows in place, When shares its row with the Note, and the attestation sits beside the proof card. This halves the When and Proof widths compared with the board. It reads cleanly and passes at 92.7, but the design engineer may prefer full-width rows with the Note below.
- **Frame, not F-09:** the top nav doesn't mark "My work" / "Projects" as current on /work/... pages (TopNav matches only destination routes), while the boards draw a white label with an orange bar. This is the same on F-03's pages. "Start work" is absent from the frame on this base.
- **Small differences:** the success h1 is 34px against the board's 36px (`.resp-title`, response.css:15); the form h1 at the same size matched, so this is low and non-blocking. "Record and continue" on the reconcile panel is disabled until a choice is made, where the board draws it enabled; that is correct behaviour. The phone "Back to my queue" and the checkbox halo show hover/focus colours from the scripted click.
- **Exception requests (none approved), with my judgement:**
  - "Start work" / "More ways to start": justified. They are frame items from F-05 that are not on this base and are outside F-09's lane.
  - SCR-02 text, complementary and "Change the reminder" items: justified for F-09. They are F-03's page (being rebuilt in F-14), and readiness PMO-0-7 keeps "Change the reminder" out. They are not approvals of F-03's page.
  - "← Queue" / "← Work item" / "← SOW": justified. These are the frame's "Back to …" accessible names, covered by D-33.
  - "20 Dec 2026, 14:10": justified. A sworn datetime input can't be static text, and the tool can't read input values (D-16).
  - "Add the proof and confirm it's genuine to record this." as role=alert: justified. It has the same words and the role is needed so screen readers announce it.
  - Proposed in build.md but not in the JSON (Note, attestation, phone When, no preselected action, STATION 3 OF 5, full version label in the phone summary, channel select only with two or more channels): all are backed by the spec's Assumptions and are needed, not omissions. The reference beside the h1 is the exception to this; it is UI-1-1.
