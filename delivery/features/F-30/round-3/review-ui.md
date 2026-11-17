VERDICT: PASS
REVIEWER: reviewer-ui
COMMIT: 3a2884d4707522db814305db68b78dc6e4fc682a

Round 3 UI review. Checked on the running build (app 4833) at 1440 and 390.

- The new top error summary on the issue step forms is the shared design-system `ValidationSummary` (`.psl-summary`, tokens `--signal-tint` / `--signal-ink`). It is not a one-off. It renders only after an invalid submit, with "2 things to fix" and links to each field, above the field-level errors that stay in place.
- Computed colours at both widths: background rgb(251,227,217), text rgb(154,47,16). These are the signal tokens and the contrast is readable.
- No horizontal overflow at 390 (scrollWidth 390). The layout holds.
- Default board states are unchanged. The summary adds no markup until a failed submit, and the other round-3 changes are an assign-option hint de-duplication and the focus helper. No fidelity re-run was needed. The round-2 fidelity results stand.

Notes: none.
