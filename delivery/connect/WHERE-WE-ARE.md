# Where we are, in plain words (25 Nov 2026, about 06:00 WAT)

## The job
Connect every approved screen of the PSL Factory app to the real backend. The app was built over 7 days against a design-version mock. The backend developer (Stanley) then shipped the real API, and since 23 Nov we have been connecting screen by screen.

## The two apps you can open
| | Port | What it is |
|---|---|---|
| **Design version** | 3000 | The approved design, running on sample data built into the app. The whole journey is clickable here (start work, RFP, planning, costing, SOW, milestones, invoices, payments). |
| **Live version** | 3002 | The same app talking to the real backend and a demo database. Only the screens connected so far work here. |

## What is connected to the real backend (about 30 of 72 pieces)
Sign-in and out, invitation set-up, My work, the factory floor, verified outputs and exceptions, alerts, the work item page (actions, station track, facts), starting a weekly report, reviewing it (Approve, Return, Refuse), the decision desk, document review, logging an RFP and assigning its PM, the project list and project pages with six tabs (Journey, Delivery, Milestones, Documents, Money/Registers/Actions), marking a milestone complete, the retrospective, issues (read-only) and the cash forecast.

## What is NOT connected yet (about 40 pieces)
Starting any work except the weekly report (minutes, issues, changes, emergencies, escalations), the RFP response and submission, engagement and planning, the costing sheet, recording the SOW signature, invoice release and intake, payments, payroll, management accounts, assets, income schedules, the Assistant, and Setup.

## How the work is being done now (lean mode, D-209 and D-210)
Usage on the weekly limit is high (80%), so there are no review agents. A builder builds, GitHub's automatic checks run (lint, types, unit tests, build), and I merge. Every merge is on the list at `delivery/connect/review-later.md` for reviewing later, by you or the factory next week. Money, sign-in and database changes still come to you.

## The demo (parked after tonight)
A backend command now fills a demo database with the design version's four projects and seven people, for showing the live app. It is a side job, and it stops once the new database is ready.

## What happens next, in order
1. Finish the demo database (a builder is on it now).
2. Back to the main job: start with starting work from the forms (F-92), so more than the weekly report can be started live. Then RFP response, engagement, planning, costing and the SOW signature (these use PSL's placeholder costing rule and engineering lead, D-214). Then invoice release and payments, then the Finance screens.
3. The Assistant needs an OpenRouter key and model name from Stanley.
