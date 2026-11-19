# Builder pre-review checklist (D-123)

Check each item before writing build.md. Each one has cost a review round before.

1. **Stale decision.** A second reviewer acting on an old copy gets a 409. They must see a lasting notice and their unsent note, with no decide buttons. Use the shared fix (F-35 971bf73a / F-39 45ae7b66, now in dlv-00). Test the real two-reviewer sequence, where the task actually closes.
2. **"Approved" or "verified" only after the re-read confirms it.** Never say it straight after a 200.
3. **Banner and tag tones come from the status tone in the data, matching the board.** Don't fall back to the warning tone by default.
4. **No extra panels.** Decided or step-less tasks get no TaskPanels card. Don't draw panels the board doesn't show.
5. **Data, not wording.** Messages are an item's `text`, never a `note` with empty items. Fixture wording must avoid words the spec bans (e.g. "received").
6. **Tap targets are at least 44×44 on phone.** Phone order matches the board, with no gaps.
7. **Disabled controls say why** (aria-describedby plus a visible line).
8. **Exceptions.** One per real difference, honestly labelled. Never use one to hide a value or a drawable element ("tool limit" only when the tool truly can't read it).
9. **Shared files** (Workspace, InlineDecide, WorkItemOverview, labels, Sections): scope every change to your line key. List each change in build.md.
10. **Fidelity.** ONE run. At 70 or above, write a waiver; don't iterate.
11. **Fixes lines** use the format `- ID | what | sha`, with plain IDs.
12. **Before handing in, the worktree is clean and pushed, and your servers are stopped.** Wait for the shared lock with a blocking background wait, not repeated polling.
- **Never remove the shared lock by hand.** Another run may hold it. Wait for it to be released (one blocking background wait).
