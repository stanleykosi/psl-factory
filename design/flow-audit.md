# End-to-end flow audit — RFP from a loan company to project closure

Date: 2026-11-12. Method: walk the flow step by step, ask the questions a PSL user would ask, answer each from the backend code (`apps/workflows/factory_*.py`, `apps/pmo/*`) and the design canvas, and record what is missing, duplicated or in conflict. Example client: Tamarind Loans Ltd (sample).

Legend: ✅ covered · 🟡 partly covered · ❌ missing screen · ⚠️ conflict or open question.

## Stage 0 — Before any work: people, roles, rules

| # | Question | Answer | Status |
|---|---|---|---|
| 0.1 | How does a new staff member get in? | Admin invites them, they set up (SCR-21, SCR-17 setup). | ✅ |
| 0.2 | Where do we say which role may do what (assign RFPs, review documents, approve costing)? | Backend reads a policy matrix (`D05.decision_action_matrix`, e.g. `rfp.assignment_roles`). Setup shows a "Rules · 13 open" tab but it was never drawn. | ❌ Setup · Rules |
| 0.3 | Where is delegation set? | Only seen inside a validation state (SCR-13). | ❌ Setup · Delegation |
| 0.4 | Where are document templates (invoice, SOW, weekly report, minutes) managed? | Test templates are referenced everywhere; no screen. | ❌ Templates |
| 0.5 | Where is a client's billing contact kept? | Start work says "add one in the project's client details" — no such page. | ❌ Client register and client details |

## Stage 1 — The RFP arrives and is bid on

| # | Question | Answer | Status |
|---|---|---|---|
| 1.1 | Where is a received RFP logged? | Start work menu → Log a received RFP (SCR-23). | ✅ (built today) |
| 1.2 | Who assigns the PM, where? | Leads see it in Unassigned → Assign PM (SCR-24). | ✅ (built today) |
| 1.3 | Where does the PM build the response — the requirements matrix (up to 100 rows, each addressed / clarification / out of scope)? | Backend needs it to start the RFP line; no screen. | ❌ RFP response workspace (requirements matrix) |
| 1.4 | How do Engineering, QA, Security, Product contribute? | Backend action `rfp.contribute:<team>`; they don't log in, so the PM records it. Could reuse Record a response (SCR-16) with a "team input" type. | 🟡 reuse SCR-16, add variant |
| 1.5 | Where is the bid priced? | Costing and commercial line: estimates, costing rule, calculation. No costing sheet screen; only the CEO decision (SCR-03 ceo-costing). | ❌ Costing sheet (estimates in, rule, result) |
| 1.6 | Who reviews the response? | PMO Lead and Engineering Lead (backend `REVIEW_ROLES`). Engineering doesn't log in. | ⚠️ conflict A |
| 1.7 | Commercial approvals? | PM → Head of PMO → CEO → PMO Lead, in order. Decision screen covers it. | ✅ screen · ⚠️ conflict B (Head of PMO) |
| 1.8 | How is the outcome recorded — won, lost, pending — and lessons if lost? | Backend `rfp.outcome` and `dispose`. No screen. | ❌ Record RFP outcome (could be an SCR-16 variant) |

## Stage 2 — Won: engagement, planning, SOW

| # | Question | Answer | Status |
|---|---|---|---|
| 2.1 | Does the PM have to be assigned again for the engagement? | Backend has a separate `engagement.assign` step even after an RFP assignment. | ⚠️ possible duplicate step — ask backend |
| 2.2 | Where do departments give scope and estimates? | Planning sends requests; owners don't log in, so PM records with proof. | 🟡 reuse SCR-16 |
| 2.3 | Where is the client's SOW signature recorded? | Record a response (SCR-16). | ✅ |
| 2.4 | When does the project appear in Projects? | After the engagement is registered. | ✅ SCR-22 |
| 2.5 | Is pricing done once (for the bid) or again after planning? | RFP needs commercial approvals before submission; SOW comes after planning. | ⚠️ ask backend |

## Stage 3 — Delivery, week to week

| # | Question | Answer | Status |
|---|---|---|---|
| 3.1 | Where does the weekly report's text come from? | The PM writes it, citing records (SCR-25); Tola assembles; PMO Lead reviews (SCR-08). | ✅ (built today) |
| 3.2 | After a meeting, where does the PM confirm the decisions and actions Tola suggested? | Backend `confirm()` needs a human; no screen. | ❌ Confirm minutes |
| 3.3 | Where do action items live — who owns them, what's overdue? | Reports count them; Registers has no Actions tab. | ❌ Actions list (project) |
| 3.4 | Where does an issue owner acknowledge and report progress? | Registers lists issues; no issue detail. | ❌ Issue detail |
| 3.5 | Change requests: assessments, decision, signatures? | Assessments recorded by PM (SCR-16 variant), decision (SCR-03), closure signatures (SCR-16). | 🟡 needs a change detail view |
| 3.6 | Emergencies? | CTO decision exists (SCR-03 cto-emergency). | ✅ |
| 3.7 | Where does leadership read the Tuesday and monthly reports? | Verified tab / document view. | 🟡 no report reader |

## Stage 4 — Each milestone: complete, invoice, get paid

| # | Question | Answer | Status |
|---|---|---|---|
| 4.1 | Where is the list of milestones for a project? | Money tab shows contract stages (SCR-12); Mark complete (SCR-19). | 🟡 no milestone list on the project |
| 4.2 | Invoice draft → review → issue → deliver → verify? | SCR-02 states, SCR-03, J-04 storyboard. | ✅ |
| 4.3 | Payment received, short payment? | SCR-20 record; shortfall stays owed until a Finance Lead decides. | ✅ |
| 4.4 | Where does the Finance Lead decide a short payment / payment exception? | Backend `payment.exception.decide`; no decision variant. | ❌ Payment exception decision |
| 4.5 | Overdue: Chidi drafts a reminder — where does Finance check and send it? | No screen. | ❌ Payment reminder (draft → send) |
| 4.6 | Month-end, bank imports? | Import (SCR-09) yes; Month-end tab drawn in nav concepts only. | ❌ Month-end |

## Stage 5 — Go-live to closure

| # | Question | Answer | Status |
|---|---|---|---|
| 5.1 | Go-live signatures? | SCR-16 records PM and client signatures. | ✅ |
| 5.2 | Who acknowledges the Support handover? | Backend: a Support recipient (`delivery.support_receive`). Support isn't a logged-in role. | ⚠️ conflict C |
| 5.3 | Where is the retrospective captured? | Closure needs a retrospective record; no screen. | ❌ Retrospective |
| 5.4 | Closure needs "Finance confirmation" — where? | Not found in code. | ⚠️ ask backend |
| 5.5 | Head of PMO decides closure. | Decision screen. | ✅ screen · ⚠️ conflict B |

## Cross-cutting

| # | Finding | Status |
|---|---|---|
| X.1 | Project pages (Journey, Documents, Money, Registers) are four separate boards with different headers — should be one project page with tabs. | 🟡 duplicate headers |
| X.2 | My work has both "Needs me" and "Decisions" — decisions are also things that need me. | ⚠️ possible duplicate tab |
| X.3 | "Exceptions" is a My work tab and the Overview page (SCR-10). Fine if one is "mine" and one is "all" — label it. | 🟡 clarify |
| X.4 | Overview page needs its own concepts (floor-strip concepts were drawn for My work). | 🟡 |
| X.5 | Payroll Corrections tab (nav concepts) has no screen. | ❌ |
| X.6 | Start work drawer is drawn for the invoice line only; the other 24 lines' intake fields are listed on the Lines page but not as drawer states. | 🟡 by design (one pattern) |
| X.7 | "Start here" board describes the old layout; old concept boards (A–D) could move to an archive page. | 🟡 tidy |
| X.8 | Start work button shows for CEO and CTO — hide if they can't start any line. | ⚠️ ask PSL |

## Conflicts between the backend and the agreed scope

- **A. Engineering Lead reviews** (RFP response, change decisions) but Engineering doesn't log in. Either give the Engineering Lead a login, or let the PM record the decision with proof (the backend may not allow a recorded decision today).
- **B. Head of PMO vs PMO Lead.** The backend treats them as two roles (commercial approvals, escalations, closure); our role list merged them.
- **C. Support acknowledges the handover** but Support doesn't log in.

## Missing screens — proposed build list (priority order)

1. RFP response workspace with requirements matrix (1.3)
2. Costing sheet (1.5)
3. Record RFP outcome, with lessons when lost (1.8)
4. Confirm minutes (3.2)
5. Actions list on the project (3.3)
6. Issue detail with owner follow-up (3.4)
7. Change detail (3.5)
8. Payment exception decision (4.4)
9. Payment reminder draft → send (4.5)
10. Retrospective (5.3)
11. Setup · Rules, Setup · Delegation (0.2, 0.3)
12. Templates (0.4)
13. Client register and client details (0.5)
14. Month-end (4.6) and Payroll corrections (X.5) — after the Finance/Payroll A/B decision
15. One project page with tabs (X.1) and a milestone list (4.1)

Built today: Log a received RFP (SCR-23), Assign the accountable PM (SCR-24), Write the weekly client update (SCR-25), corrected weekly report line flow.
