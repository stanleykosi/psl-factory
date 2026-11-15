VERDICT: PASS
COMMIT: f91bc63ff41283e698faf47b356721f4ce2ec022
REVIEWER: reviewer-ux
AUTHORITY: reviewer-ux

Scope: `git diff a5e803ab..f91bc63 -- frontend/` read only. No server run, per the cost policy. Round 2 PASS stands for everything outside this diff.

Checked, per persona and journey:
- Decide bar on phone (users who can act): the Decide panel is now fixed at the bottom. The page keeps its height clear using a measured `--ws-bar-h` plus `scroll-padding-bottom`, so the last section and Tab focus are not hidden behind it. Buttons are at least 44px tall and wrap. The heading is visually hidden but still in the DOM, so the region keeps its accessible name. The measurement is cleaned up on unmount.
- Failure notices: a failed, problem or uncertain notice now scrolls into view when the pressed control is elsewhere. This helps a phone user whose bar is fixed. The live region is unchanged and `display: contents` keeps the layout.
- Read-only and no-access personas: no change. Nothing in the diff touches permissions. The stale-read guard on an id change stops one item's data appearing on another, which is a small safety gain.
- Checklist marks removed: the status stays as a word (Done, Blocked, Held and so on). Meaning never depended on the mark, which was aria-hidden.
- Amber section note: now a warning callout with an icon and text, placed under the section. This is clearer, and it is not colour-only.
- Table and suggestion cards: money is left-aligned and plain. The table scrolls sideways on a phone and its focusable wrapper is kept. A reference and its source are no longer repeated. The suggestion label, answer and "Suggested by" are each shown once. Accept and Edit are unchanged.
- Form submit is now filled, with danger staying red. This makes the main action clearer.

Non-blocking:
1. `.ws-decide .ws-steps__buttons > span { flex: 1 1 120px }` could squeeze long step labels into wrapped text on a 320px screen. Check this in the final QA pass.
2. Left-aligned money in tables departs from the usual right-alignment, but it follows the approved board (SCR-56), so it is fine.
3. The `Cites` helper hides cites that the label already contains, by a case-insensitive text match. This is fine for now, but fragile if labels change.
