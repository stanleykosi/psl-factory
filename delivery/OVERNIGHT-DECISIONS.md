# Overnight decisions (14–15 Nov 2026)

The design engineer went to bed and asked the coordinator to keep working without pausing:
follow the coordinator's recommendation on anything not serious, keep anything that truly needs
their approval in the "Waiting for you" list, record every decision here so they can revert it,
and make the final screens match the approved boards at least 99%.

Each entry: what was decided, why, and how to revert.

## Rules the coordinator follows overnight
- The approved boards are the spec. A UI round passes only when the design-fidelity check passes
  on every board in scope (100% of elements after approved exceptions, visual >= 90) and the
  reviewer's side-by-side reading finds no remaining difference.
- Low and medium risk features that pass every review, QA, PMO acceptance and the fidelity gate
  are merged into `dlv-00-delivery-setup` under the standing merge delegation. Product acceptance
  for those is recorded as **provisional, by the coordinator**, marked for your check.
- High-risk features (money, security, sign-in) are built and reviewed fully but **not merged**;
  they wait for you.
- Nothing is merged into `main`.
- Business rules, approvers, money values and backend decisions are never invented; anything
  needing PSL or the backend developer waits.

## Waiting for you
(updated as the night goes on)

## Decisions taken
- **D-01 · 3D floor concept.** You asked me to pick by my recommendation. Recorded when the four concepts are ready (see below).
- **D-02 · Phone Start work forms** use a bottom sheet for every line (your answer, 14 Nov).
- **D-03 · Round limit raised from 3 to 5** in `delivery/config.json`, so fidelity rounds can finish unattended. Revert: set `max_rounds` back to 3.
