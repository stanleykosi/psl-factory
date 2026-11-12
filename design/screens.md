# Screen inventory

Every screen the approved journeys need, with its states and its artboards on the
canvas. One line per screen; IDs stay stable for the life of the project, and
delivery tasks reference them.

**Early start, recorded 12 Nov 2026.** These screens are being drawn before the
architecture stage, on realistic sample data, on the explicit instruction of the
design engineer (hunchoweb). The architecture package (the data API agreed with the
backend developer, assumption A-01) has not been produced yet, so each screen's
data, permissions and failure states are taken from the current backend's records
and rules and must be checked and revised once architecture is approved. This is
not a client approval and does not replace the architecture gate.

Concept: CON-C Assembly line, design system "PSL Factory". Agents: Tola (PMO),
Chidi (Finance), Zainab (HR).

Format: `- SCR-n | J-n[, J-n] | Screen title | states: … | components: CMP-n, … | artboards: …`

## Screens

- SCR-01 | J-01, J-02, J-05 | Work queue | states: default, empty, loading, error | components: CMP-01, CMP-03, CMP-05, CMP-06, CMP-07, CMP-08, CMP-16, CMP-18 | artboards: SCR-01-desktop, SCR-01-mobile, SCR-01-desktop-empty
- SCR-02 | J-01, J-04, J-05, J-07 | Work item | states: default, processing, owner-needed, effect-uncertain, verified, permission | components: CMP-01, CMP-02, CMP-04, CMP-05, CMP-09, CMP-10, CMP-14, CMP-16, CMP-18 | artboards: SCR-02-desktop, SCR-02-mobile, SCR-02-desktop-owner-needed, SCR-02-desktop-effect-uncertain, SCR-02-desktop-verified
- SCR-03 | J-02 | Decision on a phone | states: default, submitted, not-yours, stale-version | components: CMP-03, CMP-05, CMP-10, CMP-11, CMP-14, CMP-16, CMP-18 | artboards: SCR-03-mobile, SCR-03-mobile-done, SCR-03-mobile-stale
- SCR-04 | J-01, J-04 | Start work | states: default, validation | components: CMP-01, CMP-16 | artboards: SCR-04-desktop, SCR-04-mobile
- SCR-05 | J-10, J-11 | Assistant | states: default, thread, draft-started, cant | components: CMP-01, CMP-09, CMP-12, CMP-13, CMP-14, CMP-15, CMP-17, CMP-18 | artboards: SCR-05-desktop, SCR-05-desktop-thread, SCR-05-mobile
- SCR-06 | J-08 | Factory floor | states: default, reduced-motion | components: CMP-01, CMP-08 | artboards: SCR-06-desktop, SCR-06-mobile
- SCR-07 | J-08 | Project journey | states: default, empty | components: CMP-01, CMP-02, CMP-03, CMP-05 | artboards: SCR-07-desktop, SCR-07-mobile
- SCR-08 | J-01, J-02 | Document review | states: default, returned | components: CMP-01, CMP-10, CMP-16 | artboards: SCR-08-desktop
- SCR-09 | J-06 | Import and reconcile | states: default, validation, error | components: CMP-01, CMP-16 | artboards: SCR-09-desktop
- SCR-10 | J-05 | Exceptions | states: default, empty | components: CMP-01, CMP-03, CMP-05 | artboards: SCR-10-desktop, SCR-10-mobile
- SCR-11 | J-08 | Registers: issues, changes, RFPs | states: default, empty | components: CMP-01, CMP-07 | artboards: SCR-11-desktop
- SCR-12 | J-11 | Report with drill-down | states: default, loading | components: CMP-01 | artboards: SCR-12-desktop
- SCR-13 | J-07 | Setup: roles, rules and delegation | states: default, validation, permission | components: CMP-01 | artboards: SCR-13-desktop
- SCR-14 | J-01, J-04 | Verified outputs | states: default, empty | components: CMP-01, CMP-04, CMP-05, CMP-07, CMP-16 | artboards: SCR-14-desktop
- SCR-15 | J-09, J-02 | Alerts and notification settings | states: default, empty | components: CMP-01, CMP-18, CMP-19 | artboards: SCR-15-desktop, SCR-15-mobile-whatsapp, SCR-15-mobile-settings
- SCR-16 | J-03 | Record a response | states: default, validation, success | components: CMP-01, CMP-16, CMP-20 | artboards: SCR-16-desktop, SCR-16-mobile
- SCR-17 | J-02 | Sign in | states: default, error | components: CMP-21 | artboards: SCR-17-mobile, SCR-17-desktop
- SCR-18 | J-06 | Restricted payroll matching | states: default, permission | components: CMP-01, CMP-09, CMP-16, CMP-18 | artboards: SCR-18-desktop, SCR-18-desktop-permission

## Data each screen shows

Sample data until the architecture package exists. Sources are the current backend's records, named in plain terms; the API endpoints come from architecture.

- SCR-01 — work items the person may see, with line, current station, state, who it waits for, age; queue counts; floor counts per line.
- SCR-02 — one work item: stations from its line definition, the six facts, agent steps and the records they read, the current human task and decision, send jobs and receipts.
- SCR-03 — one human task: the exact version, amount and basis from contract terms, recipient, what changed, who may decide.
- SCR-04 — the lines this person may start and each line's intake fields.
- SCR-05 — conversations, the records an answer cites, drafts and the work items they start; the person's access per project.
- SCR-06 — every line, its stations and the count of items at each.
- SCR-07 — one project's work items across all lines, in order.
- SCR-08 — a document version, its template (test template for now), review state and audience.
- SCR-09 — an imported file, its rows, mapping and the rows that failed checks.
- SCR-10 — items with an uncertain send or a failed check, and what is being done about each.
- SCR-11 — issues, change requests, emergencies and RFPs with owners and states.
- SCR-12 — a report's figures and, for each, the records it came from.
- SCR-13 — roles and who holds them, rules with versions, delegations; only for roles allowed to change them.
- SCR-14 — verified outputs with their facts and receipts.
- SCR-15 — alerts sent to the person, their channel choices and quiet hours.
- SCR-16 — the step waiting for an outside response, the response, the uploaded proof and who recorded it.
- SCR-17 — sign-in only.
- SCR-18 — payroll inputs, staff-matching results and what this role may see.

## Revisions

- 2026-11-12 — inventory written; early start on sample data recorded above; journey J-02 drawn: SCR-15-mobile-whatsapp, SCR-17-mobile, SCR-03-mobile, SCR-03-mobile-done, SCR-03-mobile-stale — canvas version 1794452188-99e9.
- 2026-11-12 — concept C screens brought up to the assistant's level: Assistant tab in navigation, Chidi and Zainab avatars on agent work — canvas version 1794451999-2a67.
