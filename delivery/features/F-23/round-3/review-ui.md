VERDICT: PASS
COMMIT: d5f10f5a22b05103700b95c8c05a5cf8cdb212c7
REVIEWER: reviewer-ui
AUTHORITY: delivery UI review

## Summary
- Since a3f43067, the only frontend change is Tola's "needs you" sentence. It is now an amber warning line, chosen by data: `agent_note.warn_lines`, a fixtures-only proposal. Everything else in the range is delivery records, including the D-105 and D-106 sign-off.
- The amber is the shared `Callout kind="warning"` → `.psl-callout--warning` (`--waiting-tint` / `--waiting-ink`), the D-92b "waiting on someone" family. It is tokens only, with no new CSS and no hard-coded colour. Its icon and colour match the board's amber box.
- The tone comes from line indexes in the data. Nothing matches on the words.
- No other line screen changes. Only the W-2301, W-2306 (+ .next), W-2307 and W-2308 fixtures carry `warn_lines`. Without the key, `AgentNote` renders the same single info callout and markup as before.
- The score drops to 69.1 → 65.3 (desktop default) and 74.2 → 70.2 (phone default). That is the design engineer's recorded choice (D-106), and both waivers are signed at those scores.

## Findings
- UI-3-1 | non-blocking | low | frontend | (no board) | If every line of a note is flagged, the info callout is skipped. The amber callout then carries no agent name ("Tola"), so nothing on screen says who wrote the line (`Workspace.tsx` `AgentNote`). No fixture does this today. When the proposal goes to the backend list, either keep the name on the amber block when it stands alone, or say that at least one line must stay unflagged.
- UI-3-2 | non-blocking | low | frontend | SCR-28-desktop, SCR-28-mobile | `round-3/fidelity/scores.txt` still lists 69.1 and 74.2. The sign-off runs (`SCR-28-desktop-1440-signoff` 65.3, `SCR-28-mobile-390-signoff` 70.2, from their report.json) are not in it. Add the two rows so the record matches the signed waivers.

## Verified
- UI-2-1 | verified | carried from the earlier round-3 check: Due is a `date` column with `date_format: "day_month"`, reading "13 Nov" and "15 Nov". A-3 is `{unknown: true}` and draws the amber Unknown pill, and still does in the sign-off side-by-sides at 1440 and 390.
- UI-2-2 | verified | carried: the DRAFTED row tags and the "Drafted" status are `psl-tag--agent` (blue), checked on the rebuilt head at 1440 and 390. Since a3f43067 no drafted or review fixture has changed.
- UI-1-6 | verified | D-105/D-106: the third sentence is amber.
  - **Side-by-sides:** in `round-3/fidelity/SCR-28-desktop-1440-signoff/side-by-side.png` it sits under Tola's blue note as an amber band with the warning icon. `SCR-28-mobile-390-signoff/side-by-side.png` shows the same at 390, with no overflow.
  - **Code:** the tone comes from `warnLines(note)`, the indexes in `warn_lines` (integers only), via `Callout kind="warning"`.
  - **Scope:** `grep -rl warn_lines frontend/mock/fixtures` lists only the five W-23xx files. The other `agent_note` fixtures (W-2001, W-2201..W-2209 and sidecars) have no key, so F-17, F-21 and F-22 render unchanged.
- D-105 | verified | `fidelity-exceptions.json`: 0 of 36 exceptions are still pending. All 8 visual waivers are signed: D-105, or D-106 for the two default boards. Every waiver text matches its measured score.

## Waivers (final, one line per board)
| Board | Width | Visual | Signed | Waiver |
|---|---|---|---|---|
| SCR-28-desktop | 1440 | 65.3 | D-106 (design engineer, 16 Nov 2026) | Signed below the D-83 floor by explicit choice. The rest is the approved shared frame; no gap F-23 can fix. |
| SCR-28-desktop-suggesting | 1440 | 81.3 | D-105 | Signed. |
| SCR-28-desktop-drafted | 1440 | 85.4 | D-105 | Signed. |
| SCR-28-desktop-review | 1440 | 78.7 | D-105 | Signed. |
| SCR-28-mobile | 390 | 70.2 | D-106 | Signed. |
| SCR-28-mobile-suggesting | 390 | 82 | D-105 | Signed. |
| SCR-28-mobile-drafted | 390 | 82.5 | D-105 | Signed. |
| SCR-28-mobile-review | 390 | 78.7 | D-105 | Signed. |

## Notes
- The diff covers `Workspace.tsx` (`AgentNote` split), `proposals.ts` (`warnLines`), five fixtures, and tests: minutes.test.tsx (flagged and unflagged) and the mock-contract strip and W-23xx guard.
- The two merges of dlv-00 bring no frontend change.
- Read-only: I started no servers, changed no code, and had no test-results to delete.
