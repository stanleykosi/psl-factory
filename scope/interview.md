# Discovery interview log

Internal working notes, not sent to the client. One section per round. Record each
answer's source so scope.md never states a guess as a client decision.

## Sources received

- PSL operations factory repo (`psl-factory`, main 31a8cbd, 11 Nov 2026): Django 5.2 server-rendered app, 25 factory lines, 191 page templates, 122 process IDs (108 in this release). Read directly.
- Design reference pages in `docs/design/artifacts/`: workflow map, architecture map, PSL approvals worksheet (6–11 Nov 2026).
- Design engineer's decisions, 7–11 Nov 2026, in conversation: alerts by WhatsApp and email; staff record client responses with proof; test document templates until PSL supplies real ones; role-based factory; logged-in roles PMO, PMO Lead, Finance, Finance Lead, HR, HR Lead; leadership roles as listed; all devices; high volume of work.

## Round 1 (12 Nov 2026)

- Q1 Where do project records live — answer: in the PSL repo on branch `design/frontend-ux` (`scope/`, later `design/`) — source: design engineer accepted recommendation, 12 Nov.
- Q2 What is the project — answer: frontend and UX redesign of the existing PSL operations factory: visual system, screen layouts, navigation and states; backend rules and services unchanged, and anything the design needs from the backend goes to the backend developer as a change request — source: design engineer accepted recommendation, 12 Nov.
- Q3 Who at PSL approves scope and design — answer: one named person in a PMO leadership role approves both; name, role and approval record still to come from PSL — source: design engineer accepted recommendation, 12 Nov; name is an open question for PSL.
- Q4 Users — answer: logged in: PMO, PMO Lead, Finance, Finance Lead, HR, HR Lead; CEO and CTO login to be confirmed by PSL; Engineering, QA, Security and clients do not log in and PMO records their responses — source: design engineer, 7 and 11 Nov.
- Q5 Screens in scope — answer: the 12 screen templates (Start work, Work queue, Work item, Decision, Agent work, Document review, Import and reconcile, Exceptions, Register, Report with drill-down, Project journey, Setup) with their key states, plus My work, Verified outputs, Notification settings, sign-in, empty and error states — source: design engineer accepted recommendation, 12 Nov.
- Q6 Out of scope — answer: backend logic and rules; the 14 deferred BaaS processes; sending WhatsApp/email (designed, not connected); a client portal; PSL's real document templates; deployment — source: design engineer accepted recommendation, 12 Nov.
- Q7 Build and technology — answer: the design is built after approval, using modern frontend frameworks and motion/3D libraries (named: WebGL, GSAP, three.js, Next.js), not only server-rendered HTML and CSS; must work on phone, tablet and desktop — source: design engineer, 12 Nov. Note: the repo's architecture names a server-rendered console as primary and relies on Django's sessions, CSRF and forms; a separate Next.js frontend changes that and needs the backend developer's agreement (round 2).
- Q8 Brand — answer: if PSL has no brand guide, the visual identity is created during design and approved with it; otherwise follow PSL's guide — source: design engineer accepted recommendation, 12 Nov.
- Q9 Success — answer: a PM or Finance user finds what needs them and acts on it without help; every work item shows clearly which of drafted, approved, sent, receipt recorded and verified are true; PSL judges both in a review of the final design — source: design engineer accepted recommendation, 12 Nov.
- Q10 Deadline — answer: no fixed date — source: design engineer accepted recommendation, 12 Nov.

## Round 2 (12 Nov 2026)

- Q11 How the frontend reaches the backend — answer: separate Next.js app; Django adds a data API for the screens and keeps login, permissions and every business rule; single sign-in using Django's session on the same domain; the frontend only displays and submits people's actions — source: design engineer accepted recommendation, 12 Nov.
- Q12 Who agrees the API and when — answer: the backend developer agrees a screen-by-screen data contract in the architecture stage after design approval; designs use realistic sample data until then — source: design engineer accepted recommendation, 12 Nov.
- Q13 Motion and 3D — answer: WebGL/three.js for one signature "factory floor" overview; GSAP for transitions and state changes; dense working screens stay fast and calm; all motion respects reduced-motion settings and runs smoothly on a mid-range phone — source: design engineer accepted recommendation, 12 Nov.
- Q14 Where the frontend code lives — answer: a `frontend/` folder in the PSL repo — source: design engineer accepted recommendation, 12 Nov.
- Q15 Accessibility and browsers — answer: WCAG 2.2 AA; latest two versions of Chrome, Safari, Edge and Firefox on desktop and mobile — source: design engineer accepted recommendation, 12 Nov.

## Round 3 (12 Nov 2026)

- Confirmation of drafted journeys J-01–J-09 and rules R-01–R-06 — answer: no changes requested — source: design engineer, 12 Nov.
- Q-01 Who approves — answer: not known yet — source: design engineer, 12 Nov; stays open for PSL.
- Q-02 Do the CEO and CTO log in — answer: yes — source: design engineer, 12 Nov.
- Q-03 Brand guide — answer: PSL has none; the visual identity is created in design (S-01) — source: design engineer, 12 Nov.

## Frontier after round 2

- Settled: purpose, people, boundaries, constraints, existing assets, integrations (API with Django; WhatsApp/email designed but not connected).
- Journeys and rules: drafted from the repo's factory lines and product invariants, pending the design engineer's confirmation.
- Open for PSL: who approves (name, role, record); whether CEO and CTO log in; whether a brand guide exists.

## Round 4 (12 Nov 2026)

- Assistant — answer: its own page, as interactive as possible; it creates what PMs usually create (invoices, SOWs, and similar) and answers Finance's questions about projects — source: design engineer, 12 Nov. Recorded as S-10, J-10, J-11, R-08 in scope version 2; drafts follow normal review, per the repo's product rules.
