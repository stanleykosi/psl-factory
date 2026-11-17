VERDICT: PASS
COMMIT: d5f10f5a22b05103700b95c8c05a5cf8cdb212c7
REVIEWER: reviewer-security
AUTHORITY: delivery security review

## Summary
- Since a3f43067 there are two changes: `agent_note.warn_lines` (a proposal that exists only in fixtures) and the design engineer's sign-off of the exceptions (D-105, recorded in `delivery/OVERNIGHT-DECISIONS.md:168`). Neither touches requests, locks, confirm sets, the prefill or restricted handling.
- The warning tone comes from integer line positions supplied by the data. Nothing matches words in Tola's text. The lines render as escaped text, and a warning line grants nothing and triggers nothing.
- The contract-test guard is stricter. `warn_lines` must be integers that point to real lines before the test strips it. The "W-23xx only" test now covers it too.
- The round-3 conclusions at a3f43067 still hold: an unknown date is never shown as a real date, and no guard was weakened.

## Findings
- SEC-3-1 | non-blocking | low | frontend | Agent output loses its label when every line is flagged. At `frontend/src/features/workspace/Workspace.tsx:28-54`, the warning callout has no agent name. Only the info callout shows `agentName(note.agent)`. If `warn_lines` flagged every line, Tola's words would appear as an unlabelled warning, and a reader could take them for a system or policy message. The current fixtures flag one line out of three, so the name still shows nearby. Expected: agent-written text always shows which agent wrote it. Fix: show the agent name in the warning callout too, or keep the info callout (with the name) whenever the note has lines.

## Verified
- None of the earlier security findings are open. SEC-2-1 (non-blocking) carries forward unchanged: this diff does not touch `WorkItemOverview.tsx`.

## Impact assessment of the changes since a3f43067
- **`proposals.ts` `warnLines`.** It keeps only `Number.isInteger` entries, and anything malformed means "no warning lines". An index outside the note's lines has no effect, because the code only looks up the indexes of lines that exist.
- **`Workspace.tsx` `AgentNote`.** It renders the same `note.lines`, split into two callouts by position. No line is dropped or duplicated, and no HTML is injected. `announce={false}` on the warning matches the info note, so no new live-region noise.
- **`mock-contract.test.ts`.** The stripping runs only after it asserts that every index is an integer from 0 up to `lines.length - 1`. The W-23-only test now includes `warn_lines`.
- **`fidelity-exceptions.json`.** Only the `approved_by` fields changed, to "design engineer, 16 Nov 2026 — D-105". That decision is recorded in `delivery/OVERNIGHT-DECISIONS.md:168`. No secrets, no instructions in the evidence.
- **Fixtures.** W-2301, W-2306, W-2306.next, W-2307 and W-2308 each add `warn_lines: [2]`. No other change.
