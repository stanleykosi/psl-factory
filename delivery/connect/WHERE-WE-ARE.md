# Where we are, in plain words (25 Nov 2026, about 15:00 WAT)

## The job
Connect every approved screen of the PSL Factory app to the real backend. The app was built over 7 days against a design-version mock. The backend developer (Stanley) then shipped the real API, and since 23 Nov we have been connecting screen by screen.

## The two apps you can open
| | Port | What it is |
|---|---|---|
| **Design version** | 3000 | The approved design, running on sample data built into the app. The whole journey is clickable here (start work, RFP, planning, costing, SOW, milestones, invoices, payments). |
| **Live version** | 3002 | The same app talking to the real backend and a demo database. Only the screens connected so far work here. |

## What is connected to the real backend (about 38 of 72 pieces)
Sign-in and out, invitation set-up, My work, the factory floor, verified outputs and exceptions, alerts, the work item page (actions, station track, facts), starting a weekly report, reviewing it (Approve, Return, Refuse), the decision desk, document review, logging an RFP and assigning its PM, the project list and project pages with six tabs (Journey, Delivery, Milestones, Documents, Money/Registers/Actions), marking a milestone complete, the retrospective, issues (read-only) and the cash forecast. Added since: clients and client pages, starting work from forms (issues, escalation, emergency, change, minutes), the RFP response workspace, the RFP submission pack, engagement and planning (read, assign, register), the costing sheet with its approvals, and the client's response and SOW signature.

## What is NOT connected yet (about 40 pieces)
Invoice release and intake, the planning writes (department inputs, effort review, readiness, handoff), client testing and team inputs, the leadership report and payroll starts, payments, payroll, management accounts, assets, income schedules, the Assistant, and Setup.

## How the work is being done now (lean mode, D-209 and D-210)
Usage on the weekly limit is high (80%), so there are no review agents. A builder builds, GitHub's automatic checks run (lint, types, unit tests, build), and I merge. Every merge is on the list at `delivery/connect/review-later.md` for reviewing later, by you or the factory next week. Money, sign-in and database changes still come to you.

## The demo (parked after tonight)
A backend command now fills a demo database with the design version's four projects and seven people, for showing the live app. It is a side job, and it stops once the new database is ready.

## What happens next, in order
1. Done: the demo database, the start forms, and the whole RFP-to-SOW path (RFP response, submission pack, engagement and planning, costing, SOW signature), on PSL's placeholder costing rule and engineering lead (D-214).
2. Next: invoice release and payments (F-90, F-94), then the Finance screens (payments, month-end, management accounts, payroll).
3. The Assistant needs an OpenRouter key and model name from Stanley.
