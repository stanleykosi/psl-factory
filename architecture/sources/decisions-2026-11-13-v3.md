# Contract fields for the approved boards, 13 Nov 2026 (third note)

Said by the design engineer on 13 Nov 2026, after PMO readiness for F-02, F-03 and F-04
found that the API contract (architecture v3) does not carry values the client-approved
SCR-01, SCR-02 and SCR-03 boards show.

1. Contract fields for the boards: the frontend drafts the contract fields the approved
   boards need, and the backend developer confirms them. Until confirmed they are
   proposals the frontend builds against with the contract mock; the backend developer
   may change their shape or placement.
2. Decision variants parked: the short-payment (payment exception), CEO final costing and
   CTO emergency decision variants are parked until PSL and the backend developer settle
   the payment-exception rule. The standard decision (approve, return, reject; stale
   version; not yours; own work) goes ahead without them.

## 14 Nov 2026 (design engineer)
- (c) Remove the visible SAMPLE DATA tags from the screens ("we know that"). The data stays marked `sample: true` in the contract and mock, and a build setting (NEXT_PUBLIC_SHOW_SAMPLE_LABEL=1) can show the tag again for a demo. This narrows scope item S-09 ("clearly labelled as sample data") for the team's own builds; any build shown to PSL or other outside viewers should turn the tag back on.
