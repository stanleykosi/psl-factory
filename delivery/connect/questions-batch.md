# Questions for the design engineer (batched, D-180)

Lanes append here; the coordinator brings them about twice a day and writes the answers back.

## Lane A

### F-61 · Alerts list, drawer and alert settings on the live API (SCR-15 default and settings)
Context: live `GET /notifications` and `/me/alert-preferences` are much smaller than the boards (spec `delivery/features/F-61/spec.md`, "Conflicts with the boards"). F-61 is parked until these are answered.
1. Alert rows have no agent avatar, name or time in live (A-42). (a) Recommended: show title over subject and detail, no avatar, no time. (b) Keep a neutral PSL mark in the avatar slot so the board's row alignment holds. (c) Wait for the backend to add `at` and `agent`.
2. Settings without per-event switches, digest and quiet hours (A-44). (a) Recommended: only the Email and WhatsApp switches, with Ready state and receipts. (b) Also show the old rows greyed out, "Not available yet". (c) Hold the settings page until the backend decides.
3. Search, agent filter, unread filter and totals (A-43). (a) Recommended: remove them for this release; show "N alerts loaded" with the as-of time. (b) Keep an unread-only toggle and text search over the loaded list, worded "filtered from the loaded alerts". (c) Keep the full toolbar and wait for paging.
4. The recent-deliveries list is new on the settings board. (a) Recommended: a plain list under the switches. (b) A one-line summary of the last delivery per channel. (c) Leave receipts out until the board is redrawn.
5. An alert with no usable link (no work id in its link). (a) Recommended: the row is not clickable and has a Mark as read button. (b) The row stays clickable and only marks it read. (c) Hide such alerts.
6. Wording of the receipt states. (a) Recommended: Queued, Not confirmed, Delivered, Held. (b) Waiting to send, Could not confirm, Delivered, On hold. (c) Your own wording.
7. D-ALERTS-ENTRY, the part still open: the account menu's "My roles" and "Delegate while away" links lead nowhere, and no phone board shows how the account page (password change, SCR-15 account boards) opens. (a) Recommended: for now the account menu shows only the person's name and Sign out (as F-58 built it), and the phone menu gets an "Account" row opening `/settings/account`; draw "My roles" and "Delegate while away" later. (b) Draw both links now, pointing at the setup screens. (c) Leave the account tab unbuilt this release.

## Lane B

- **F-74 · B1. Setup without a workspace (backend B-21, short-list 4).** Every live Setup read and save needs a workspace; our Setup pages are organisation-wide. How should Setup open?
  1. (Recommended) Setup opens with a workspace picker; rules, delegation and templates show for the chosen workspace. We ask the backend which workspace holds organisation-wide values and switch when they answer.
  2. Wait for the backend to add an organisation-level Setup read before connecting Setup.
  3. Pin Setup to one named workspace that PSL chooses.
  Context: we are building the picker now (option 1) so Setup is not held up; options 2 and 3 only change which workspace it opens on.

- **F-74 · B2. Workspace picker on the Setup frame (not on the boards yet).** A picker at the top of Setup, filled from your active projects, choosing which workspace's rules, delegation and templates you see.
  1. (Recommended) Approve a simple picker in the Setup header, with the chosen workspace kept in the address so reload and links work.
  2. Draw it on the canvas first, then build.
  Context: needed whichever way B1 goes, unless one fixed workspace is chosen.
- **F-74 · B3. Setup saves become "draft, then review".** Live never puts a rule or delegation change straight into force; it is saved as a draft that someone reviews and activates. Every save also needs a proof file, and the backend has not said how the screen creates one (B-25).
  1. (Recommended) This release connects Setup reads only; the Save, Edit and Replace controls stay visible but disabled with the line "Changes open once proof upload is connected", and we build the draft-and-review step when the backend answers.
  2. Build "Saved as draft, waiting for review" now and hold only the final send.
  3. Hide the edit controls entirely until then.
- **F-73 · B4. Clients without an amount owed.** In live a client is a group of workspaces with no owed amount, money panel or "blocked" lines.
  1. (Recommended) Hide the owed column, money panel and blocked lines for now.
  2. Keep them and show "Not available in the live data yet".
- **F-73 · B5. Client id in the address.** Live has no client id. The page address would use the group key (or the workspace id when a project has no group); the key can change if grouping changes.
  1. (Recommended) Accept the group key in the address.
  2. Use a name in the address and look it up.
- **F-73 · B6. Adding a billing contact waits.** Adding a billing contact needs a proof file and the shared "attach proof" picker does not exist yet (backend question 1).
  1. (Recommended) Connect the client reads now and keep "Add billing contact" disabled with the reason, in a later feature.
  2. Hold the whole Clients connection until the picker exists.
- **F-72 · B7. Document review parts with no live source.** Live has no agent notes per section, "changed since" marks, Compare, per-check Done/Held/Blocked list, project reference or TEST TEMPLATE tag; the returned banner is a status word only.
  1. (Recommended) Drop those parts for this release; show the returned state as its status text, and the crumb from the project title alone.
  2. Keep them as "Not available yet" placeholders.
- **F-72 · B8. Reject and the approve note.** Live offers approve, return and reject, and requires a note on approve.
  1. (Recommended) Offer approve and return as drawn, require the note on approve as live does, and leave reject out until you draw it.
  2. Add a Reject button now with the same note box.

- **F-70 · B9. Project list and journey: nine board changes from live data.** Full options in `delivery/features/F-70/spec.md` ("Conflicts with the boards"). We build option 1 of each; say "accept all" or name the ones to change.
  1. (Recommended) Accept all: project list loses the next-milestone column, reference, count badges and rows-per-page (shows "N shown, more available"); the journey loses "What is next", Tola's summary and "Station n of m"; the facts strip has four cells (invoices verified and paid have no live source) with "Figures may be partial." when finance is partial; the Delivery tab is hidden and its address says "not available yet"; work tags are one neutral colour with the live words; no tab counts; started and updated times are shown on each work row.
  2. Keep the missing parts as "Not available" placeholders instead of removing them.
  Context: each gap has a backend question (B-2 to B-6, B-33, B-34); we switch them on when answered.

## Lane C

### LC-Q1 · F-85, F-87 · Work item parts the live API does not give
The approved work item shows a station track (who holds each step), the six facts strip (drafted, reviewed, approved, sent, receipt, verified) and the agent's numbered steps. Live `GET /work/{id}` has none of these (backend question 2). What should the page show until the backend answers?
1. **(Recommended)** Hide the three parts. Show what live gives instead: the state tag, next step, why it is stuck (`blocker`), the current activity line, and the link to the finished output.
2. Keep the three parts on the page with a plain "not available yet" note.
3. Build our own station track from the history list. This is an engineering guess, not a backend fact, and it may show the wrong holder.

### LC-Q2 · F-87 · "Confirm what happened" after an uncertain send
In the design, a person with recovery authority chooses delivered, not delivered or unknown and attaches proof. In live, reconcile is only a backend lookup: the person presses it and the backend decides (backend question 10).
1. **(Recommended)** Show one "Check what happened" button that runs the lookup, then show the state it comes back with. Keep the choice-and-proof panel out until the backend answers.
2. Keep the panel visible but disabled, with a note that it is waiting on the backend.

### LC-Q3 · F-86 · Lines Start work cannot submit yet
Some lines say `can_submit_via_api: false`, and the invoice start is not among the live lines (backend question 8).
1. **(Recommended)** List those lines as unavailable with a one-line reason, and leave out the invoice start until the backend answers.
2. Hide them from the chooser completely.

### LC-Q4 · F-85 · History list: filters, counts and sentences
The approved History view has per-filter counts, rows written as sentences with an actor kind, and "show more". Live `GET /work/{id}/history` returns at most 30 rows of `{at, station, status, actor?, reason?, evidence_id?}`, filtered only by worker, decision or evidence, with no counts and no paging (backend question 5).
1. **(Recommended)** Keep the filter tabs but drop the counts and "show more"; write each row from `station` and `status` words plus the actor and reason when present; say "Showing the latest 30" with the as-of time.
2. Hide the filters too and show one list.
3. Hold History until the backend adds counts and paging.

### LC-Q5 · F-85, F-87 · Buttons the boards draw that this feature leaves out
The work item boards draw Resume, Cancel and "Confirm what happened" buttons and the decision card. Their writes are in F-87 and the decision screen is a separate feature. Until F-87 merges the page shows no write buttons (decisions waiting link to their own page).
1. **(Recommended)** Leave the buttons out until F-87 merges; the page shows state, next step and blocker only.
2. Show them disabled with "Not available yet".

### LC-Q6 · F-85 · Fields the boards show that live does not give
Reference (for example "INV-0412"), started by, started at and amount have no live source on `GET /work/{id}` (backend question 7, A-14). Live gives the work id, `owner` and `updated_at`.
1. **(Recommended)** Drop reference, started by and amount; show "Updated" from `updated_at` and "With" from `owner` when there is one.
2. Show the numeric work id as the reference.
