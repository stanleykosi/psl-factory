# Migration brief: move built screens onto the shared components (D-91, D-92)

Read first: `delivery/design-system-conformance/audit.md` (the findings, by id),
`delivery/design-system-conformance/components-build-note.md` (the library, its calls and
"what the migration must watch for"), `frontend/src/components/README.md`, and D-91/D-92 in
`delivery/OVERNIGHT-DECISIONS.md`. The design system: `design/system/project/README.md`,
`tokens.json`, `components/`.

## Do, for every file in your lane
1. Replace hand-written design-system markup with the shared components from `@/components`
   (Button, Callout, Tag/StateTag, Panel, fields, Segmented/Tabs, Menu/SplitButton, SearchField,
   ListToolbar/FilterPanel, Drawer/BottomSheet/Dialog, FileUpload, ShowMore, Table, Loading/Empty/
   Error states, PageTitle, VisuallyHidden, useIsPhone, the date/money formatters and Values).
   Delete the feature's private copies once nothing uses them (duplicate hooks, formatters,
   InfoIcons, visually-hidden classes, ProofFields, phone hooks).
2. Fix every audit finding (groups A, B, D, E and the C rows) whose file is in your lane:
   - A: sizes, type, spacing, radii, motion, z-index from tokens (incl. the new D-92a tokens).
   - B: colour meaning per the README; "Effect uncertain" is amber everywhere.
   - D: state words only from the README list; "Unknown" is the word, never 0/blank/—;
     dates "17 Nov 2026" / "14:30 WAT"; money with two decimals unless a board shows otherwise.
     SAMPLE DATA tags stay off in team builds (14 Nov decision (c)) — don't turn them on.
   - E: 44px targets on phones; focus-visible; keyboard per the component; correct live roles.
3. Keep behaviour: no change to requests, guards, idempotency, permissions or the uncertain-send
   lock. No change to `architecture/`, `src/api/`, `package.json`/lock. Mock fixtures only if a
   test needs the shape the component expects (say why).

## Prove nothing got worse
- `bash delivery/checks.sh` passes; the e2e specs for your lane's features pass.
- Tests: update only what the components legitimately change (e.g. `getByRole('combobox')` for
  Select, no `role="alert"` on warning callouts, ISO date values) and list every changed assertion
  with its reason; never weaken an assertion.
- Fidelity: re-run the design-fidelity check once at the end on every board your lane's features
  were scored on (their feature folders list boards, drivers and exceptions files; use each
  feature's own exceptions). For each board give before (the feature's last recorded score) and
  after. A drop is allowed only when it comes from a D-92 decision (colour meaning, 44px on phones,
  500px drawer) — name it; any other drop is a bug to fix.
- List every place where the page now differs from its board because of the design system
  (colour, wording, size) so the design engineer can see them in one list.

## Housekeeping
`npm ci` in your worktree's frontend/ (never link or copy node_modules). Check
`df -h /System/Volumes/Data` before heavy steps; stop under 3 GB. Use only your lane's ports.
FRAME_FIXTURES=1 for review copies; stop your servers by PID; delete test-results. Commits
descriptive, no Co-Authored-By, no AI footer; push your branch (retry; never force; never main);
no PR. Write your note to `delivery/design-system-conformance/lane-<n>-build-note.md` in the MAIN
folder with STATUS:, COMMIT: (full sha), BRANCH:, BUILDER:, LANE:. Report any permission refusal
instead of working around it.
