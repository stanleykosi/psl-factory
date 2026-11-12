# Scope: PSL operations factory — frontend and experience redesign

VERSION: 2
Client: PSL Product Studio
Prepared by: PSL factory design engineer (hunchoweb)
Date: 2026-11-12

## Summary

- A new frontend for the PSL operations factory: the place where PMO, Finance and HR teams start work, follow it through each station, make decisions and see verified results.
- It replaces the look, layout, navigation and every screen state of today's app with a designed visual identity, built as a modern web app that works on phone, tablet and desktop.
- The business rules, permissions and records stay exactly as the current backend defines them; the new frontend shows them clearly and lets people act on them.
- It matters because the factory only works if people can see what needs them and act on it quickly, and if no one ever mistakes a draft for an approval, or a sent invoice for a paid one.

## Goals and success measures

- G-01 PMO and Finance users find what needs them and act on it without help — measured in PSL's review of the final design: a PM and a Finance user each complete their main journey on the prototype unaided.
- G-02 Nobody confuses the stages of a piece of work — measured in the same review: reviewers correctly say, for sample work items, which of drafted, approved, sent, receipt recorded, verified and paid are true.
- G-03 PSL has a visual identity it is proud to show — measured by PSL's approval of the design system with the final design.
- G-04 Work keeps moving when someone is away from a desk — measured by an approver completing a decision on a phone in the review.

## Users and roles

- U-01 PMO (project managers) — start and follow project work, record responses from clients and from teams that don't log in, mark milestones complete; see only the projects and actions their role allows.
- U-02 PMO Lead — everything a PMO user does, plus reviews documents before they go to clients, approves plans and other PMO decisions, and handles PMO setup; must not approve Finance decisions.
- U-03 Finance — prepares invoices, imports and reconciles month-end data, follows up payments; must not approve its own work where a Finance Lead decision is required.
- U-04 Finance Lead — approves Finance decisions and handles Finance setup.
- U-05 HR — matches staff and business-unit records for payroll in a restricted area; sees only the staff fields HR is allowed to share.
- U-06 HR Lead — approves HR corrections and decides which staff fields Finance may see.
- U-07 CEO — logs in to give final approvals that are the CEO's, such as final costing.
- U-08 CTO — logs in for the decisions that are the CTO's, such as emergency changes for the most serious incidents.
- U-09 People who don't log in (Engineering, QA, Security, Product and clients) — their estimates, sign-offs and responses are recorded in the app by PMO, with proof attached.

## Journeys in scope

- J-01 A PM starts a piece of work so that it moves through every station to a verified result — from "Start work" to seeing it marked verified.
- J-02 An approver acts on a decision from an alert so that work isn't held up — from a WhatsApp or email alert to approving, returning or rejecting one exact version, on a phone or a desktop.
- J-03 A PM records an outside response so that the factory has the evidence it needs — from a client's or team's reply to a recorded response with proof attached.
- J-04 Finance prepares an invoice so that a completed milestone is billed correctly — from the milestone completion notice to the invoice issued, delivered and verified.
- J-05 A user deals with an exception so that nothing is sent twice or lost — from a work item flagged "effect uncertain" to it being reconciled and moving on.
- J-06 HR matches staff for payroll so that Finance gets accurate totals without seeing private details — from the payroll inputs to a reviewed, restricted result.
- J-07 A Lead clears a stop so that held work resumes — from a work item showing "Owner needed" or "Setup needed" to the missing role or rule being set and the work continuing.
- J-08 Anyone with access checks a project's whole journey so that they know where it stands — from a project to one view of every line it has passed through and what is next.
- J-10 A PM asks the assistant to create an invoice, SOW or other document so that a draft is ready without assembling it by hand — from a request in plain words to a draft in the right line, waiting for its normal review.
- J-11 A Finance user asks the assistant about a project so that they get an answer without chasing the PM — from a question to an answer that cites the records it came from, using only records they may see.
- J-09 A user sets their own alert preferences so that they get what they need without noise — from their settings to choosing WhatsApp, email or both and how often.

## In scope

- S-01 A visual identity and design system for the factory: colour, type, spacing, icons, components and motion rules, approved by PSL.
- S-02 Concepts on a Claude Design canvas, built from fetched inspiration, mixed section by section, with one direction chosen by PSL.
- S-03 Every screen and state for the journeys above, designed on the canvas: Start work, Work queue, Work item, Decision, Agent work, Document review, Import and reconcile, Exceptions, Register, Report with drill-down, Project journey, Setup, My work, Verified outputs, Notification settings, sign-in, and empty and error states.
- S-04 For each work item state (ready, processing, waiting, owner needed, setup needed, action needed, effect uncertain, awaiting reconciliation, verified, cancelled), a designed screen state that says what is happening and what to do next.
- S-05 A "factory floor" overview showing the lines, stations and work moving through them, using 3D and motion.
- S-06 Designs for WhatsApp and email alerts and the in-app notification centre.
- S-07 A reusable "record a response" step for responses from clients and from teams that don't log in.
- S-08 The approved design built as a new frontend app in the `frontend/` folder of the PSL repo, using Next.js, GSAP and three.js/WebGL, working with the existing backend through a data API.
- S-10 An assistant page where PMO, Finance and HR users ask, in plain words, for answers about work they can see and for new drafts of what they usually prepare (invoices, SOWs, plans, reports, minutes, client messages); each draft starts in its normal line and waits for the usual review, and every answer shows where it came from.
- S-09 Realistic sample data for designs and early builds, clearly labelled as sample data.

## Out of scope

- OUT-01 Changes to business rules, approvals, calculations or permissions — these stay with the backend; anything the design needs from it goes to the backend developer as a separate change.
- OUT-02 Building the backend data API — the backend developer builds it; this project defines what each screen needs from it.
- OUT-03 The 14 BaaS processes, deferred from this release — the navigation leaves room for them.
- OUT-04 Actually sending WhatsApp and email messages — the alerts are designed, but connecting the providers is a later step.
- OUT-05 A client portal — clients stay outside the app for now and staff record their responses.
- OUT-06 PSL's real document templates — designs use clearly labelled test templates until PSL supplies its own.
- OUT-07 Deploying to a live server and live provider connections.
- OUT-08 Decisions about who holds each role, delegation rules and deadlines — these come from PSL through the approvals worksheet.

## Constraints

- C-01 Works on phone, tablet and desktop; PSL cannot predict which devices people will use.
- C-02 Meets WCAG 2.2 level AA accessibility.
- C-03 Supports the latest two versions of Chrome, Safari, Edge and Firefox on desktop and mobile.
- C-04 Motion and 3D run smoothly on a mid-range phone and respect each person's reduced-motion setting; dense working screens stay fast and calm.
- C-05 Built with Next.js, GSAP and three.js/WebGL in the `frontend/` folder; the existing Django backend keeps login, permissions and every business rule, and people sign in once.
- C-06 Designed for a high volume of work: many projects, invoices and decisions at once.
- C-07 No fixed deadline.

## Business rules

- R-01 Drafted, reviewed, approved, sent, receipt recorded, verified and paid are always shown as separate facts; no screen merges them.
- R-02 An unknown value is never shown as zero.
- R-03 Work done by an agent never looks like a person's approval.
- R-04 Each person sees and can act on only what their role allows, checked by the backend for every record and action.
- R-05 Project planning and costing come before the signed SOW.
- R-06 Anything shown as sample, test or mock data is visibly labelled.
- R-07 A send whose outcome is unknown is checked before anything is resent.
- R-08 The assistant only uses records the person asking may see, shows the source of every answer, and anything it creates is a draft that goes through the usual reviews and approvals; it never approves, sends, pays or changes a record on its own.

## Integrations and data

- I-01 PSL operations factory backend (Django and PostgreSQL) — the source of every record, decision and permission; owned by PSL, maintained by the backend developer.
- I-02 A data API on that backend for the new frontend — contents agreed screen by screen with the backend developer after design approval.
- I-03 WhatsApp Business and email — alert channels; designed in this project, connected later; accounts to be owned by PSL.
- I-04 Claude Design canvas — where concepts, screens and the design system are made and reviewed.

## Assumptions

- A-01 The backend developer will agree to build a data API for the new frontend — the design engineer chose a separate Next.js frontend; the repo's current console is server-rendered.
- A-02 The same person at PSL approves both this scope and the final design — PSL has not named anyone yet.
- A-03 Approvers who work in other systems, such as production deployment approvals in GLPI, keep doing so there; the app records the reference — this is how the backend works today.
- A-05 "Create a score" in the design engineer's request is read as creating a SOW — likely a transcription of "SOW"; to be confirmed.
- A-04 Designs can start on sample data before the backend API exists — the screens need realistic data, not live data.

## Open questions

- Q-01 | open | Who at PSL approves this scope and the final design, and where will the approval be recorded? — PSL

## Change log

- Version 1: first draft for client review.
- Version 2: added the assistant page (S-10), its journeys (J-10, J-11) and rule (R-08), at the design engineer's request on 12 Nov 2026.
