# Decisions relayed by the design engineer, 14 Nov 2026

Recorded as said in the build session; project inputs, not authenticated approvals.

- (c) Remove the visible SAMPLE DATA tags from the screens ("we know that"). The data stays marked `sample: true` in the contract and mock, and a build setting (NEXT_PUBLIC_SHOW_SAMPLE_LABEL=1) can show the tag again for a demo. This narrows scope item S-09 ("clearly labelled as sample data") for the team's own builds; any build shown to PSL or other outside viewers should turn the tag back on.
- (d) Build the remaining frontend screens in parallel (design engineer, 14 Nov 2026, "go"): FE-M2 splits into FE-M2A (Start work) and FE-M2B (responses and exceptions); FE-M3 splits into projects, overview/floor/reports, Finance/payroll and setup; each depends only on what it uses (the app frame, or the work item page for responses), and FE-M4 depends only on the app frame. Ordering only; no endpoint, decision or business rule changes.
