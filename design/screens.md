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

**Every screen and every state has both a desktop and a phone version** (design engineer, 12 Nov 2026; serves C-01). The alert's desktop counterpart is the email alert.

Format: `- SCR-n | J-n[, J-n] | Screen title | states: … | components: CMP-n, … | artboards: …`

## Screens

- SCR-01 | J-01, J-02, J-05 | Work queue | states: default, my-work, empty, loading, error | components: CMP-01, CMP-03, CMP-05, CMP-06, CMP-07, CMP-08, CMP-16, CMP-18 | artboards: SCR-01-desktop, SCR-01-mobile, SCR-01-desktop-empty, SCR-01-mobile-empty, SCR-01-desktop-my-work, SCR-01-mobile-my-work
- SCR-02 | J-01, J-04, J-05, J-07 | Work item | states: default, ready, processing, waiting, setup-needed, awaiting-reconciliation, cancelled, owner-needed, effect-uncertain, verified, permission | components: CMP-01, CMP-02, CMP-04, CMP-05, CMP-09, CMP-10, CMP-14, CMP-16, CMP-18 | artboards: SCR-02-desktop, SCR-02-mobile, SCR-02-desktop-owner-needed, SCR-02-mobile-owner-needed, SCR-02-desktop-effect-uncertain, SCR-02-mobile-effect-uncertain, SCR-02-desktop-verified, SCR-02-mobile-verified, SCR-02-desktop-processing, SCR-02-mobile-processing, SCR-02-desktop-permission, SCR-02-mobile-permission, SCR-02-desktop-ready, SCR-02-mobile-ready, SCR-02-desktop-waiting, SCR-02-mobile-waiting, SCR-02-desktop-setup-needed, SCR-02-mobile-setup-needed, SCR-02-desktop-awaiting-reconciliation, SCR-02-mobile-awaiting-reconciliation, SCR-02-desktop-cancelled, SCR-02-mobile-cancelled
- SCR-03 | J-02 | Decision on a phone | states: default, submitted, not-yours, stale-version | components: CMP-03, CMP-05, CMP-10, CMP-11, CMP-14, CMP-16, CMP-18 | artboards: SCR-03-desktop, SCR-03-mobile, SCR-03-desktop-done, SCR-03-mobile-done, SCR-03-desktop-stale, SCR-03-mobile-stale, SCR-03-desktop-not-yours, SCR-03-mobile-not-yours, SCR-03-desktop-ceo-costing, SCR-03-mobile-ceo-costing, SCR-03-desktop-cto-emergency, SCR-03-mobile-cto-emergency
- SCR-04 | J-01, J-04 | Start work | states: default, validation | components: CMP-01, CMP-16 | artboards: SCR-04-desktop, SCR-04-mobile, SCR-04-desktop-validation, SCR-04-mobile-validation
- SCR-05 | J-10, J-11 | Assistant | states: default, thread, draft-started, cant | components: CMP-01, CMP-09, CMP-12, CMP-13, CMP-14, CMP-15, CMP-17, CMP-18 | artboards: SCR-05-desktop, SCR-05-mobile, SCR-05-desktop-thread, SCR-05-mobile-thread, SCR-05-desktop-draft-started, SCR-05-mobile-draft-started, SCR-05-desktop-cant, SCR-05-mobile-cant
- SCR-06 | J-08 | Factory floor | states: default, reduced-motion | components: CMP-01, CMP-08 | artboards: SCR-06-desktop, SCR-06-mobile
- SCR-07 | J-08 | Project journey | states: default, empty | components: CMP-01, CMP-02, CMP-03, CMP-05 | artboards: SCR-07-desktop, SCR-07-mobile
- SCR-08 | J-01, J-02 | Document review | states: default, returned | components: CMP-01, CMP-10, CMP-16 | artboards: SCR-08-desktop, SCR-08-mobile, SCR-08-desktop-returned, SCR-08-mobile-returned
- SCR-09 | J-06 | Import and reconcile | states: default, validation, error | components: CMP-01, CMP-16 | artboards: SCR-09-desktop, SCR-09-mobile, SCR-09-desktop-error, SCR-09-mobile-error
- SCR-10 | J-05 | Exceptions | states: default, empty | components: CMP-01, CMP-03, CMP-05 | artboards: SCR-10-desktop, SCR-10-mobile
- SCR-11 | J-08 | Registers: issues, changes, RFPs | states: default, empty | components: CMP-01, CMP-07 | artboards: SCR-11-desktop, SCR-11-mobile
- SCR-12 | J-11 | Report with drill-down | states: default, loading | components: CMP-01 | artboards: SCR-12-desktop, SCR-12-mobile
- SCR-13 | J-07 | Setup: roles, rules and delegation | states: default, validation, permission | components: CMP-01 | artboards: SCR-13-desktop, SCR-13-mobile, SCR-13-desktop-validation, SCR-13-mobile-validation, SCR-13-desktop-permission, SCR-13-mobile-permission
- SCR-14 | J-01, J-04 | Verified outputs | states: default, empty | components: CMP-01, CMP-04, CMP-05, CMP-07, CMP-16 | artboards: SCR-14-desktop, SCR-14-mobile
- SCR-15 | J-09, J-02 | Alerts and notification settings | states: default, empty | components: CMP-01, CMP-18, CMP-19 | artboards: SCR-15-desktop, SCR-15-mobile, SCR-15-desktop-email, SCR-15-mobile-whatsapp, SCR-15-desktop-settings, SCR-15-mobile-settings
- SCR-16 | J-03 | Record a response | states: default, validation, success | components: CMP-01, CMP-16, CMP-20 | artboards: SCR-16-desktop, SCR-16-mobile, SCR-16-desktop-validation, SCR-16-mobile-validation, SCR-16-desktop-success, SCR-16-mobile-success
- SCR-17 | J-02 | Sign in | states: default, error | components: CMP-21 | artboards: SCR-17-mobile, SCR-17-desktop, SCR-17-desktop-error, SCR-17-mobile-error
- SCR-18 | J-06 | Restricted payroll matching | states: default, permission | components: CMP-01, CMP-09, CMP-16, CMP-18 | artboards: SCR-18-desktop, SCR-18-mobile, SCR-18-desktop-permission, SCR-18-mobile-permission

- Shared states | all lists and reports | Empty, loading and error pattern for SCR-01, 07, 10, 11, 12, 14, 15 | artboards: STATES-desktop, STATES-mobile

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
- 2026-11-12 — journey J-01 drawn: SCR-01-desktop, SCR-04-desktop, SCR-02-desktop, SCR-14-desktop, SCR-01-desktop-empty, SCR-01-mobile, SCR-04-mobile, SCR-02-mobile — canvas version 1794452604-bb02.
- 2026-11-12 — journeys J-05 and J-07 drawn: SCR-02-desktop-effect-uncertain, SCR-10-desktop, SCR-02-desktop-verified, SCR-02-desktop-owner-needed, SCR-13-desktop, SCR-10-mobile — canvas version 1794452766-2d6f.
- 2026-11-12 — journeys J-03 and J-06 drawn: SCR-16-desktop, SCR-16-mobile (validation), SCR-09-desktop, SCR-18-desktop, SCR-18-desktop-permission — canvas version 1794453313-75d1.
- 2026-11-12 — pairs rule applied: every desktop board got its phone board and vice versa (SCR-01, -02, -03, -04, -09, -10, -13, -14, -15 email, -16, -17, -18 and their states) — canvas version 1794453704-1e94.
- 2026-11-12 — journeys J-08 to J-11 drawn in pairs: SCR-06 factory floor, SCR-07 project journey, SCR-11 registers, SCR-12 report drill-down, SCR-15 notifications and alert settings, SCR-05 assistant and conversation, SCR-08 document review. Design lint: ready for client approval — canvas version 1794454032-781f.
- 2026-11-12 — states that carry a rule drawn in pairs on the new "States" page: SCR-02 processing and no access, SCR-03 not yours, SCR-04 and SCR-13 validation, SCR-05 draft started and can't share, SCR-08 returned, SCR-09 file error, SCR-13 view only, SCR-16 recorded, SCR-17 sign-in error; plus one shared empty/loading/error pattern (STATES-desktop, STATES-mobile).
- 2026-11-12 — scope gaps closed: all ten work-item states from S-04 (added ready, waiting, setup needed, awaiting reconciliation, cancelled), "My work" as the queue's "Started by me" tab, and decisions for the CEO (final costing) and CTO (emergency change), each in desktop and phone, on the page "Work-item states, My work, CEO and CTO".
