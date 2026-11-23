DECISION: READY
RISK: medium
SURFACES: ui, api, contract-change
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- Connects the already-built, design-approved SCR-06 Overview (F-08, route `/overview`, `src/features/overview/*`) to live `GET /overview`, task FE-CONNECT-1. It is read-only and one PR.
- The live shape is much smaller than v7: `lines[{key, title, total}]`. The four totals, station counts, line status tags and the 8-floor grouping do not exist live.
- Open questions A-33 to A-36 are not blockers. D-180 says to build on the best reading and flag them.
- Product acceptance is required because the floor loses data the client has seen (see Scope).

## Scope
Outcome: a lead, CTO or CEO sees the factory floor from live overview records, with the coverage time, and opens the work behind each line.

In:
- Replace the v7 overview read with `GET /overview` through the live client. Show `as_of` as "Updated at".
- One row per authorised line from `lines[{key, title, total}]`. Keep a local, versioned map from line key to floor group (8 floors, with the subtitle and avatar text), as A-35 suggests. Map the keys the backend returns. Show an unmapped key under a plain "Other lines" floor and never drop it.
- Say what `total` means in plain words, "recorded work for this line", until A-33 is answered. Do not call it "open" or "in progress".
- Unknown is never 0. Omit the four headline totals, the station counts, the "needs a person" marks and the status tag colour and label. Show an explicit "Not available yet" state where the design has them. Never compute or invent them from `total`. Keep the 3D floor and the flat reduced-motion view working on this reduced data.
- Open the work behind each count with `GET /work?line=<key>`, using the existing SCR-01 queue and no new screen.
- States: loading, empty (no authorised lines), error with retry, and 403. A 403 is a state ("you don't have access to the overview") that follows the server's decision. Do not add a client-side role check beyond hiding the nav entry if the session already says so.
- Remove the v7 mock path for `/overview`, and update the tests to cover each state above.

Out: any backend change, SCR-10 exceptions, SCR-14 verified outputs, any write, and invented counts, tags or role rules.

Endpoints: `GET /overview`, drill-down `GET /work?line=`. Source: `delivery/connect/screens-a-frame-core.md`, "SCR-06 · Overview: factory floor".

## Risk
Medium because it is a cross-layer contract change that drops design content (totals, stations, tags) and rests on an assumed key-to-floor mapping. The mapping must not mislead on counts. It is read-only, so it moves no data, money or identity, and the server decides who can read it. Surfaces are ui, api and contract-change. The product-acceptance gate covers the reduced floor, so the product-decision surface is not added.
