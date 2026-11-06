# First connected factory path: planning to Finance

Start with demonstrable factory work from intake to a verified downstream output: requirements and Engineering/Security estimate evidence → detailed plan/costing → versioned SOW/cost decisions and document review → signed baseline → PMO milestone completion → durable Finance handoff. This proves connected agent/human operational flow, not just navigation through forms. Include scoped agent execution, interrupted/restarted work, human waits and receipt verification. It is not a product scope ceiling. Continue into the remaining families after reviewing results.

## Build together
- Factory UI: follow one work item through intake, agent preparation, current station, required costing/document decisions, PMO completion and the Finance handoff receipt/next task. Show ownership, dependencies, waits, rework and verified outputs. Case timelines, plan/cost/SOW evidence, forms and configuration provide supporting detail.
- Real domain services/PostgreSQL transactions: versioned evidence, source-prescribed costing order, signed-baseline reference, PMO completion and atomic outbox, worker lease/restart and idempotent delivery.
- Agents: O01 coordinates allowed tasks; A02 extracts cited facts; A04 manages missing-evidence/internal handoff tasks; A05 explains Finance evidence; A08 checks independently specified expectations. Start provider integration with a contract-faithful fake for deterministic tests, then add real-provider evaluation as part of the full product, not a later optional AI feature.
- Policy interfaces: actual costing rule references, role assignments, document templates, schedule terms and payment assessment/exception configuration. Missing values are visible; dependent operational effects wait, but interfaces, screens and tests are implemented.

Use synthetic input first. The known costing chain remains PM → Head of PMO → CEO; document quality review is distinct. Planning precedes signature. PMO completion creates Finance notification, not Finance approval of completion or automatic recognition/invoicing. Signed SOW opens the billing stage; exact UAT/completion billing triggers are configurable.

Primary initial behavior touches P03, P06–P12, P16–P21, P25, P26, P34, P52, P53, P63 and F34 (21 IDs), with supporting controls P01/P02/P05/P22–P24/F33 and P14 evidence discovery. This is partial coverage; retain the full process contracts and finish the remaining behavior later.

Run tests/acceptance.json including M1-29: one connected actual staff/request → PostgreSQL → outbox → worker restart → adapter/inbox → agent audit path using the same case/evidence IDs. Mock external providers/adapters, not internal services, ORM, permissions or transactions. Record results and advance the backlog; do not mark entire processes complete from this one demo.
