# Questions for the design engineer (batched, D-180)

Lanes append here; the coordinator brings them about twice a day and writes the answers back.

## Lane A

### F-60 · Account set-up from an invitation (SCR-17 set-up boards, `/staff/join/`)
Context: live accept needs a confirm field, does not sign the person in, and answers every unusable invitation the same way (spec `delivery/features/F-60/spec.md`). F-60 builds on F-58 and is parked until these are answered.
1. Confirm password: the API needs it; the boards draw one field. (a) Recommended: add "Confirm new password" under "New password". (b) One field with a show-password toggle, sending the same value as confirm (a typo is not caught).
2. WhatsApp number block (no operation, G-SCR17-5). (a) Recommended: leave it out, as D-177 did for removed content. (b) A disabled field, "Not available yet".
3. Password hint "At least 12 characters" (no rule in the API, A-47). (a) Recommended: no hint; after a refusal the server's message shows. (b) A hint with no number: "Choose a password that's hard to guess."
4. After "Finish setup" (not drawn; the backend does not sign them in). (a) Recommended: "Your account is ready. Sign in with <email>." with a Sign in button to `/sign-in`. (b) Ask the backend to sign them in on accept (backend change, and the admission call A-48). (c) Go to `/sign-in` with a small "Your account is ready" note (changes F-58's page).
5. The invitation's end date (live gives `expires_at`). (a) Recommended: one secondary line, "This invitation works until 26 Nov 2026, 15:00." (b) Leave it off, as the board.
6. Welcome line when the invitation gives several workspaces with different access. (a) Recommended: one sentence per access group. (b) A short list under "You've been given:".
7. Wording for a link that cannot be used (no board). (a) Recommended: "This invitation can't be used. It may have expired or already been used. Ask the person who invited you to send a new one." plus "Already set up? Sign in". (b) The same without the sign-in link.
8. Name in the welcome line (boards say "Sola"; live gives the full name). (a) Recommended: the name as returned. (b) The first word only.

### F-61 · Alerts list, drawer and alert settings on the live API (SCR-15 default and settings)
Context: live `GET /notifications` and `/me/alert-preferences` are much smaller than the boards (spec `delivery/features/F-61/spec.md`, "Conflicts with the boards"). F-61 is parked until these are answered.
1. Alert rows have no agent avatar, name or time in live (A-42). (a) Recommended: show title over subject and detail, no avatar, no time. (b) Keep a neutral PSL mark in the avatar slot so the board's row alignment holds. (c) Wait for the backend to add `at` and `agent`.
2. Settings without per-event switches, digest and quiet hours (A-44). (a) Recommended: only the Email and WhatsApp switches, with Ready state and receipts. (b) Also show the old rows greyed out, "Not available yet". (c) Hold the settings page until the backend decides.
3. Search, agent filter, unread filter and totals (A-43). (a) Recommended: remove them for this release; show "N alerts loaded" with the as-of time. (b) Keep an unread-only toggle and text search over the loaded list, worded "filtered from the loaded alerts". (c) Keep the full toolbar and wait for paging.
4. The recent-deliveries list is new on the settings board. (a) Recommended: a plain list under the switches. (b) A one-line summary of the last delivery per channel. (c) Leave receipts out until the board is redrawn.
5. An alert with no usable link (no work id in its link). (a) Recommended: the row is not clickable and has a Mark as read button. (b) The row stays clickable and only marks it read. (c) Hide such alerts.
6. Wording of the receipt states. (a) Recommended: Queued, Not confirmed, Delivered, Held. (b) Waiting to send, Could not confirm, Delivered, On hold. (c) Your own wording.
7. D-ALERTS-ENTRY, the part still open: the account menu's "My roles" and "Delegate while away" links lead nowhere, and no phone board shows how the account page (password change, SCR-15 account boards) opens. (a) Recommended: for now the account menu shows only the person's name and Sign out (as F-58 built it), and the phone menu gets an "Account" row opening `/settings/account`; draw "My roles" and "Delegate while away" later. (b) Draw both links now, pointing at the setup screens. (c) Leave the account tab unbuilt this release.

### F-62 · Verified outputs and All exceptions on live GET /work (SCR-14, SCR-10)
Context: live `GET /work` rows carry no proof, reference, kind or totals (spec `delivery/features/F-62/spec.md`, "Conflicts with the boards"). F-62 is parked until these are answered; F-63 (My work) reuses its list adapter.
1. How do people reach Verified outputs? (a) Recommended: a "Verified" link under the My work heading area for now (a tab-style link to `/verified`; F-63 decides the final place), no top-bar change. (b) Add "Verified" to the top bar for everyone (shell change, the boards' top bar has no such item). (c) Leave `/verified` URL-only until F-63.
2. SCR-14 Facts earned and Proof columns, no data in the list. (a) Recommended: hide both and rely on Open output. (b) Show the column headers with "Open the item to see" text (adds clutter). (c) Read each row's work item to fill them (up to 8 extra reads per page, slow, partial).
3. Heading counts "6 of 28" (SCR-14) and the open-exceptions count (SCR-10). (a) Recommended: show "{n} shown" only, plus "so far" while more pages exist. (b) Hide any count. (c) Count only the loaded rows and call it the total (wrong when more exist).
4. "Since 11:02" on exceptions becomes "Last updated". (a) Recommended: keep the board's position under the tag, wording "Last updated 11:02". (b) Drop the time from the tag cell and keep one "Last updated" column. (c) Keep the word "since" (misleading).
5. Exception kind filter chip. (a) Recommended: remove; line filter only. (b) Keep a state filter applied to loaded rows only (hides rows that exist on later pages). (c) Wait for A-38 before building the filter at all.
6. Coverage line ("may be incomplete", "n more items are still being checked") appears on both pages, not drawn. (a) Recommended: a quiet secondary line under the list. (b) A callout above the list. (c) Hide it (the list then looks complete when it is not).
7. Exception rows that are not exceptions (ready, waiting, verified) can come back on this queue. (a) Recommended: show them with their own tag. (b) Hide them on the client (the list then differs from what the server reports and the "shown" count undercounts). (c) Show a "Not an exception" tag.
8. `action_needed` tag word. (a) Recommended: "Action needed", the existing state-tag word and the board's. (b) "Blocked", the old v7 wording (no board draws it).

### F-64 · Decision desk on the live API (SCR-03 default, done, not-yours, stale, own)
Context: the live decision needs one evidence item the boards never draw, and live has no chain, basis, preparer, reason or next-step text (spec `delivery/features/F-64/spec.md`, checked against the desktop boards). F-64 is parked until these are answered.
1. Evidence picker (not on any board). The live decision needs one evidence item. Options: (a) a short radio list under the verdict buttons, labelled by source and version, nothing pre-selected, buttons off until one is picked (recommended: smallest, honest); (b) a drop-down in the note area; (c) pre-select the newest item (rejected: A-18 unanswered, would cite evidence the person did not choose).
2. Own board (prepared by you) and the "why you cannot decide" sentence. The live read has no reason and no preparer. Options: (a) show the not-yours board with the generic sentence for every case and leave the own board unreachable until the backend answers A-19 (recommended); (b) show a softer "You can't decide this one" without any reason; (c) hold the read-only boards and show only the facts.
3. Approval chain strip ("your step 2 of 3"), basis line, "what changed since last version" list, prepared-by name. No live source (A-19, A-21). Options: (a) hide each part and show nothing in its place (recommended); (b) show the row with "Not available yet" in the value; (c) keep the part but fill it only from what exists (on the stale board, version, amount and recipient comparison only).
4. Comment box on the not-yours board. The live comment write exists but `can_comment` is not exposed, so we cannot tell who may comment. Options: (a) show the box only on the read-only board and let the server's 403 turn it off (recommended); (b) hide the box until the backend says who may comment; (c) show comments as read-only text only.
5. Recipient change warning. Live data has `recipient_change{earlier,current}`, no board draws it. Options: (a) a single line in the amount/recipient rows when it changed (recommended); (b) a warning callout above the rows; (c) leave it out.
6. Decided-by on the done board. The reply has no decider or time. Options: (a) take actor and time from the decision history and hide the line if missing (recommended); (b) drop "decided by" always and keep only verdict and note; (c) show the signed-in person's name and the page's own clock time (rejected: not a record).
7. Pager "decision 2 of 5" and the phone bar's queue note. Options: (a) drop it unless the live decision list loads and contains this task, then fill from that list (recommended); (b) drop it always; (c) show the list count only ("5 waiting").
8. Parts of the done board with no live source: "Next step. Chidi will issue it and email it to…", "Paid is tracked separately…" sentence, the SENT/RECEIPT strip detail, and the "Still waiting on you" list. Options: (a) keep the "Paid is tracked separately" sentence (fixed policy copy), hide the Chidi next-step sentence and fill the "Still waiting on you" list and "Next decision" link from `GET /work?queue=decisions` only, hiding them if the list fails (recommended); (b) hide the whole "what happens next" block; (c) replace the next step with the work state label from `work_state`.
9. Stale board sentence "Version 3 was drafted at 10:46 after the billing contact changed" and the agent note "Chidi redrafted it…". The live read has no draft time, cause or agent note. Options: (a) say "A newer version arrived while you were reading. Version 2 can no longer be approved." and drop the time, cause and agent note; the comparison table (amount, recipient) stays (recommended); (b) add the time of the reload as "seen at hh:mm"; (c) keep the agent block empty.
10. Not-yours board: the "Ada Okafor was alerted at 10:42 by WhatsApp and email" line, the "You hold Finance on this project…" reason, and the BASIS value. No live source. Options: (a) keep the heading "Not your decision", the amount, "Waiting for {task.role}" and the comment box; hide the alert line, reason and basis (recommended); (b) show the line "Not available yet" in each; (c) hide the comment box as well (Question 4).
11. Default board sentence "Only a Finance Lead can decide. You are Finance Lead." Options: (a) draw "Only a {task.role} can decide." from the task and drop "You are …" because the page may not infer the person's role from /me (recommended); (b) drop the sentence; (c) fill "You are …" from /me (rejected: INV-ACCESS says /me does not decide what is offered).
12. Own board (Finance canvas) shows "Prepared by Bisi Ade (you) · with Chidi", "Asked: Ada Okafor · Finance Lead 12 Nov 10:20" and "Waiting · Finance reviewer". Preparer, asked person and time have no live source (A-19, A-21). Options: (a) leave the board built but unreachable, as in Question 2 (recommended); (b) reach it only when a later backend answer provides a `prepared_by_you` flag; (c) show it with the three lines hidden.

### F-65 · Overview, the factory floor, on live GET /overview (SCR-06)
Context: live gives one recorded-work total per line, no in-progress/needs-a-person/stopped totals, no station counts and no floor grouping (spec `delivery/features/F-65/spec.md`). F-65 is parked until these are answered.
1. The four headline totals (IN PROGRESS, NEED A PERSON, STOPPED, VERIFIED THIS MONTH) and the phone's two-figure summary; the live API returns none (A-34). (a) Recommended: keep the board's place but show one line "Totals are not available yet." (b) Hide the whole block until the backend adds them. (c) Show the four labels with "Not available yet" under each.
2. Station squares and "needs a person" marks on each row; the live API has no stations. (a) Recommended: remove the squares and show each line as a title, a number and an "Open work" link. (b) Draw one square per line with its `total`, in the neutral colour only. (c) Hide the station track and keep only the floor's sum.
3. The tag on each row (Stopped, Waiting, Verified and so on). (a) Recommended: a neutral "Not available yet" tag. (b) Hide the tag column. (c) Replace it with the recorded-work count as a tag.
4. The eight floors are rebuilt from our own key-to-floor map, and PMO lines have no floor. (a) Recommended: a ninth "Other lines" floor, shown last, with no avatar. (b) Add a "PMO" floor with a new subtitle and an existing avatar. (c) Show one flat list of lines with no floors.
5. The 3D floor has no stations to show. (a) Recommended: one machine per line with its total, neutral colour, strip with an "Open work" link. (b) Keep the 3D switch but show one block per floor with the floor's sum. (c) Hide the 3D view for this release and show flat only.
6. Strip opened from a square in the flat view lists the station's work (design D-165). (a) Recommended: remove it; "Open work" goes to the queue for that line. (b) Keep a small inline strip showing the line's count and the same link.

### F-66 · Assistant on the live conversation API (SCR-05)
Context: live has no image upload, thread titles, status badges, step lines or paging (spec `delivery/features/F-66/spec.md`). F-66 is parked until these are answered.
1. Image attach (board shows it on the composer). The live API has no upload. Options: (a) remove the control entirely and record a deviation (recommended); (b) keep it disabled with "Not available yet"; (c) keep it and send nothing (the image would be dropped silently; not advised).
2. Thread titles and status badges in the list (boards show a title and a Working / Answered / Can't / Drafted tag). Live rows have neither. Options: (a) show "<Agent> · Project|Department · Updated <time>" and no badge (recommended); (b) keep a badge slot that fills only after opening the thread; (c) fetch every thread to derive a badge, which is up to 25 extra reads per list view.
3. "What I did" step lines under an answer (boards draw them). No live field. Options: (a) hide them (recommended); (b) show the sources as the only evidence line; (c) wait for the backend.
4. Polling and the working card (board "working" shows run start and progress). Options: (a) working card with "Asked at <time>" and polling at 3 s then 10 s (recommended); (b) manual "Check again" button only; (c) polling with no card text beyond a spinner.
5. @mention picker (project, work, document, person). Replaced by the source picker (labels only). Options: (a) replace as built (recommended); (b) keep a text-only "#" shortcut that opens the same source list; (c) hide the control until sources are richer.
6. Cannot-answer card (board shows a reason and buttons). Live gives status text only. Options: (a) show the text as the reason, with a "Ask a different question" focus button only (recommended); (b) drop the reason line; (c) keep the board's suggestion buttons using `question_options`.
7. Separate person and agent bubbles with edit (board). Live has one object per question. Options: (a) two bubbles per message, no edit (recommended); (b) one card with question above answer; (c) keep edit disabled with a tooltip.
8. Conversation list paging (board shows page size). Live has none, max 25. Options: (a) remove the size control and show "<n> loaded" (recommended); (b) keep a size control that cuts the client list; (c) show "Latest 25" as a fixed label.

### F-59 · Forgotten password: ask for a link, set a new password (SCR-17 reset boards)
Context: the reset boards draw only "ask" and "Check your email."; live gives no link validity and one answer for every unusable link (spec `delivery/features/F-59/spec.md`). Q4, Q5 and the confirm field in Q2 follow D-182's answers to F-60 Q4, Q3 and Q1, so they are settled; Q1, Q2 (building the undrawn state), Q3, Q6 and Q7 are new. F-59 builds on F-58; until these are answered it is parked.
1. Link validity in the ask sentence. The board says the link "works for 30 minutes"; the API returns no validity (A-47).
   - (a) Recommended: "Enter your work email. If it has an account, we'll send a reset link." (no duration, same call as D-177 for removed numbers).
   - (b) "...we'll send a reset link that works for a short time." (hints at expiry without a number).
2. The new-password state has no board (the reset boards draw only "ask" and "Check your email.").
   - (a) Recommended: build it from the sign-in form column and the set-up pattern ("Choose a new password", two fields, "Change password"), then review it at the fidelity run.
   - (b) Hold the page until a board is drawn (the whole flow stays unusable meanwhile).
   - Same as F-60 Q1 for the second "Confirm new password" field (the API needs `new_password2`): recommendation there is to add it; here it is built as in F-60 Q1(a), to be changed with it.
3. The unusable-link state has no board.
   - (a) Recommended: heading "This link can't be used", text "It may have expired or already been used. You can ask for a new one.", primary link "Send me a new link", text link "Back to sign in".
   - (b) The same without the "Send me a new link" button (only "Back to sign in").
   - (c) Name the exact reason (not possible: the API answers the same for every reason). Same pattern as F-60 Q7; the wording here differs because the next step is asking again, not asking an administrator.
4. After the change (no board; the backend does not sign the person in).
   - Same as F-60 Q4, with the recommendation (a): a plain "Your password is changed." state with a "Sign in" button to the F-58 page. It is drawn as heading and text rather than a success callout (D-151).
5. Password hint line under "New password" (A-47).
   - Same as F-60 Q3: recommended (a) no hint; after a refusal the server's message shows.
6. "Use a different email" on "Check your email." (not drawn).
   - (a) Recommended: keep the small text button so a mistyped address can be fixed without reloading.
   - (b) Remove it; the person uses the browser back button or reloads (matches the board exactly).
7. F-58's plain "Forgot your password?" exception. The sentence returns to the drawn link in this feature.
   - (a) Recommended: link only, no helper words, centred as D-178 placed the sentence.
   - (b) Keep a helper line such as "We'll email you a link." under it (adds copy the boards do not draw).

### F-58 · Product acceptance of sign-in (PR https://github.com/stanleykosi/psl-factory/pull/100)
Context: every review passed on head `57ae81e8` (see merge-batch.md). Product acceptance is yours to give.
1. Accept F-58 sign-in and sign-out as built on `57ae81e8`? (a) Recommended: accept, and approve the merge. (b) Accept, but first make sign-out load `/sign-in` fresh (SEC-1-1, a small fix round). (c) Request changes (say which).

### Lane A · API 1.24.0 presentation questions (D-185)
Context: the re-specs on 1.24.0 switch the hidden parts back on; only these presentation choices are new. Each has a recommendation first. F-60 has no new question (its ready state is D-182 F-60 Q4).

**F-59 (forgotten password)**
8. Where the 30-minute and 12-character figures come from (new with 1.24.0; presentation only).
   - (a) Recommended: show them as the board draws, kept in one constants file that names backend answer A-47, because the API returns no value for either. The page never enforces them.
   - (b) Show them only once the backend returns them in a response (the figures stay hidden; the board's lines are missing until then; not recommended since PSL has stated the policy).

**F-61 (alerts)**
7. Wording of the daily summary line (new, A-44; presentation only). Options: (a) recommended: "Today, 23 Nov: 3 need you, 2 new updates, 1 older unread" as one quiet line above the groups, plain text, no card; (b) a small three-figure strip (Need you / New today / Older unread); (c) show only the "need you" figure.
8. Paging control on `/notifications`. Options: (a) recommended: a "Load more" button under the list with "Showing N loaded, M unread"; (b) numbered pages using `page`; (c) infinite scroll.
9. Rows with no agent or time (reminders and older alerts). Options: (a) recommended: neutral avatar slot and no time, so the row alignment holds; (b) no avatar and no time (compact rows); (c) show "Earlier" instead of a time.

**F-65 (Overview)**
7. Totals and squares are sampled from the 50 most recent items. (a) Recommended: show "at least N" and a coverage line "Counted from the 50 most recent items you can see" when limited. (b) Show the number plain with a small "(sample)" mark. (c) Hide the four totals when limited.
8. The row tag is still not supplied, but `stopped` and `needs_person` are now known per line. (a) Recommended: keep the neutral "Not available yet" tag until the backend gives a status. (b) Derive the tag in the page: "Stopped" if `stopped` > 0, "Waiting" if `needs_person` > 0, else none. (c) Hide the tag column.
9. The floor number (exact, open work) and the station squares (sampled) can disagree. (a) Recommended: show both with the footnote saying station figures come from recent items. (b) Show the floor number only when station figures are not limited. (c) Show the sum of station counts as the floor number, with the same "at least" rule.


**F-66 (Assistant)**
1. Sent images in the thread. The API returns only image ids on a message. Options: (a) "<n> images attached" text (recommended); (b) fetch the case file list and show thumbnails from `download_url`, one extra read per thread; (c) show nothing after send.
2. "Drafted" in the list. The list status cannot say drafted. Options: (a) no Drafted badge in the list, only in the thread (recommended); (b) show "Answered" with a small draft mark after opening; (c) read each thread (up to 25 extra reads).
3. Department thread entry. Options: (a) a "Whole department" switch on the new-conversation sheet, default off, with the chosen project as the anchor (recommended); (b) a separate "Department chat" button; (c) hide department scope.
4. `held` wording. The backend gives no reason. Options: (a) one fixed sentence "I couldn't complete this. Try again, or check that you still have access to this project." (recommended); (b) shorter "I couldn't answer this."; (c) show the raw status.
5. "Answered <time>" from `finished_at` on settled cards, not in the boards. Options: (a) show it small under the answer (recommended); (b) leave it out.
6. Image chips use local thumbnails before send and a remove button. Options: (a) as written (recommended); (b) filename-only chips.

### F-67 · App frame and API client on API 1.24.0 (role words, menu links, one CSRF retry, signed-out downloads)
Context: A-1 to A-5 and A-55 (backend-answers.md); the menu now varies by account (destinations[].available). Spec `delivery/features/F-67/spec.md`. F-67 builds after the main-green hotfix F-68.
1. Wording when a keyed write fails `csrf_failed` twice (and for keyless writes). Recommendation: "Your session could not be refreshed. Reload the page and try again. Nothing was changed." in the existing error spot or toast. Alternative: keep the old "Your session was refreshed. Press the action again. Nothing was changed." for keyless writes only.
2. Role words: recommendation is names only, as the boards draw (A-1 also offers mode and workspace). Alternative: add workspace as small text in the account-menu header.
3. A 429 or 503 message from the server is shown as the server writes it. Recommendation: show it as is in the existing error or toast spot. Alternative: a fixed PSL sentence with the server text as the reference line.
4. When a download hits a signed-out session, recommendation: replace the main area with the signed-out callout (as on `/me`). Alternative: a toast with a Sign in link that keeps the page.

### Lane A · line workspaces: F-69 Emergency change (SCR-50), F-121 Escalation (SCR-51), F-122 Leadership report (SCR-52)
Context: these three build on lane C's F-85 page and line adapter and also need lane C's F-87 (command and reconcile seam); F-122 also needs F-86 (start-work registry). Each spec lists "Conflicts with the boards" (parts the live read has no source for are not drawn: no names or times on decisions, no Tola cards, no attempt counts; upload proof becomes a pick from existing evidence). Accepting the recommendations below accepts those conflicts too. Backend gaps LA-1 to LA-3 are in backend-questions.md.

**F-69 Emergency change (spec `delivery/features/F-69/spec.md`)**
1. Refused board without the refuser's name, time and reason: draw only "CTO refused the preauthorisation." (recommended), or leave the refused board empty until the backend adds them?
2. Proof on the record, review and retrospective forms: a plain list of existing evidence ("Deploy log · version 1") (recommended), or hide the forms until an upload route exists?
3. Authorise confirmation: a small yes/no step before sending (recommended), or send on the first press?
4. Retrospective role: a two-choice radio "Engineering Lead / Product" shown on the form (recommended), or a dropdown?
5. Report review buttons: "Approve report / Return report / Refuse report" (recommended), or only Approve and Return?
6. Follow-up changes: show the list and the create form on the retrospective board only (recommended), or also on the report board?

**F-121 Escalation (spec `delivery/features/F-121/spec.md`)**
1. Board status tags: (recommended) keep the page's state tag only, and put a small panel heading that names what is waiting on this person ("Your decision", "Your review") only when a decision or review control is drawn; or derive the six tags from `stage` once the backend lists its values. Reason: `stage` has no enum.
2. Direction and target wording: (recommended) "Escalate to the client" exactly as the board for `escalate`/`Client`, and "Escalate to PMO", "Escalate to CTO", "De-escalate to {target}" for the rest; or show the raw values with a label. These three phrases are new copy; the client may want to confirm them.
3. A `reject` offered in `review_verdicts` (the board has Approve and Return only): (recommended) draw nothing for it; or add a third "Refuse" button with the same required note.
4. Delivery block placement: (recommended) below the message and receipts, collapsed to one line until a job exists; or in the right column on desktop beside Next.
5. History list: (recommended) draw it as a compact list under the message on every board, as the read serves it (up to 30); or only the newest decision, as the boards show.
6. "Return for rework" label: (recommended) that wording; or "Send back to the issue owner" (not recommended: it names a person the read does not).

**F-122 Leadership report (spec `delivery/features/F-122/spec.md`)**
1. Setup: page or drawer? Recommendation: the Start work drawer form (the same shell as every other line in F-86 and the SCR-04 start boards), with the SCR-52 setup artboard's fields and sentences inside it. Alternative: a full page at `/overview/leadership-reports/new` as the setup artboard draws, with the drawer line opening it.
2. Counts block on the review board: recommendation a plain six-row list ("Meetings 41 in this report" ... "Not recorded") under the board's headline, as the facts strip, with "As of" beneath. Alternative: keep the board's four large figure tiles for the domains that exist and show the other domains as small grey "Not recorded" tiles.
3. Review order of buttons: recommendation Approve and send, Return with a note, then Refuse as a quiet text button (the board draws two buttons only). Alternative: hide Refuse until a note is typed.
4. Coverage tags on sections: recommendation a small tag beside each heading ("Supported", "Partly supported", "Unknown", "Not applicable") using the existing CMP-10 status tag tones (verified, held, neutral). Alternative: only show a tag when coverage is not "supported".
5. The "left out" sentence on drafting and review: recommendation a muted line under the state/facts, naming projects. Alternative: a held-tone callout.
6. "Open the full report" link: the contract serves no report page for `document_version_id`. Recommendation: draw nothing now and add the link when the document review page for this version is chosen (it is not built for live). Alternative: link to F-85's `output_url` only once verified (this spec does that for the received board).

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

- **F-74 · B10. Setup board changes from live data.** Full list in `delivery/features/F-74/spec.md` ("Conflicts with the boards"). We build option 1.
  1. (Recommended) Accept all: workspace picker in the header (B2); edit controls visible but disabled (B3); templates lose line, TEST TEMPLATE tag, updated by, version count and kind; delegation is a read-only list of role, names and dates (no reason or status); rules lose per-row Edit, "holds N pieces of work", effective from, used by and the roles count ("not set" stays); a new "You can't open this workspace's Setup" state on each tab.
  2. Keep the missing parts as "Not available" placeholders.
- **F-73 · B11. Clients board changes from live data.** Full list in `delivery/features/F-73/spec.md`. We build option 1.
  1. (Recommended) Accept all: owed column, money panel and blocked lines removed (B4); the list mixes client groups and projects with no group, same row design; a client group has no single billing contact until the backend answers (each project links to its own contacts); small read-only "Project contacts" and "Show history" blocks; the billing contact form is disabled with its reason (B6); an "Unknown" state tag in the neutral style.
  2. Leave out the added "Project contacts" and "Show history" blocks.

- **F-72 · B12. Document review small board changes.** Details in `delivery/features/F-72/spec.md`. We build option 1.
  1. (Recommended) Accept all: on phone, Approve opens the same note sheet as Return (live needs a note on approve); the desktop note label becomes "Note for the PM"; a blockers list shows only when live reports blockers (explains why approve is refused); a "Not the current version" tag shows only on an older version.
  2. One-tap Approve on phone with a fixed note (not recommended: the note would not be the person's words).

- **F-76 · B13. Staff accounts: a read-only list now?** Who holds Admin (D-ADMIN-AUTHORITY) is still waiting for PSL, so invite, deactivate, restore and role changes cannot be built. Live can list staff and open one person.
  1. (Recommended) Build a read-only staff list and person page now, with no write controls. The board's people count, "Last signed in", invite and deactivation dates and "role per workspace" wording have no live source and are left out. Who may open it follows the server's answer (backend A-53).
  2. Wait for PSL's Admin decision and build the whole screen at once.
- **F-77 and F-78 (for PSL, no action from you):** the costing rule page waits on D-COSTING-RULE, and "Mark a milestone complete" waits on who may press it and whether it starts the invoice draft (the live command now exists). Both are parked as BLOCKED.

- **F-79 · B14 to B17. Month-end and payments list board changes.** Details in `delivery/features/F-79/spec.md`. We build option 1 of each.
  1. (Recommended) Accept all: B14 the agent notes, next-action button, "received this month", bank-data date, coverage sentence, row and filter counts, milestone label, per-row colour and month-end "N of M" are hidden (no live source), the strip gains a "data as of" cell and the State filter keeps the five live states; B15 "overdue by" becomes AGE ("N days") until the backend says what overdue means; B16 a "Partial result" notice when the data is partial, the basis beside each figure, one total per currency and basis, and month-end cash reads "By project" when it is not one figure; B17 the reminder, record-payment and review-payment actions show disabled with a reason when the server gives no link.
  2. Keep the missing parts as "Not available" placeholders.

### Batch 2 (lane B)

- **F-76 · B18. A person page that no board draws.** Live gives each person's access workspace by workspace (`GET /staff/{id}`), but SCR-21 draws only the list.
  1. (Recommended) Add a plain read-only person page at `/setup/staff/<person>` in the existing Setup style: name, status and access per workspace. We build this now.
  2. No person page; the list only, and the per-workspace access is not shown.
  Context: no write controls either way; invite, deactivate and roles wait for PSL (D-ADMIN-AUTHORITY).

### Batch 3 (lane B)

Plain hides in these two specs are covered by D-182 and are not asked again. We build option 1 of each item below.

- **F-71 · B19. Money and Milestones tabs: live data the boards do not draw.**
  1. (Recommended) Show the "figures may be partial" warning, a "Due <date>" line, several invoices per stage as a stacked list, and invoice rows that are not contract stages.
  2. Show none of them (the table matches the boards, but partial figures carry no warning).
  3. Show only the partial-figures warning.
- **F-71 · B20. Milestones tab for someone who may not see Finance figures.**
  1. (Recommended) Show the recorded completions plus one line: "Contract amounts, invoices and payments aren't available to your role."
  2. One empty state and no completions.
  3. Hide the Milestones tab for them.
- **F-71 · B21. "Recorded completions" list.** Completions and contract stages can't be joined in live (backend B-47).
  1. (Recommended) A separate list under the table.
  2. Leave it out (people without Finance figures then see nothing).
- **F-71 · B22. Paid column wording.** Live gives amounts only, no paid word.
  1. (Recommended) "Paid <amount> · Owed <amount>", with Unknown for each missing amount.
  2. A dash when both are missing (hides the unknown; not recommended).
- **F-75 · B23. Severity "Critical" in Registers.** The boards draw Low/Medium/High; live also sends Critical.
  1. (Recommended) Its own neutral tag with the live word.
  2. Show it as High.
  3. Hide Critical rows.
- **F-75 · B24. Escalations register.** Live returns an Escalations section that no board draws.
  1. (Recommended) Leave it out of the register switch for now.
  2. Add a fifth register (needs a board).
  3. Fold it into Issues.
- **F-75 · B25. Changes, Emergencies and RFPs columns.**
  1. (Recommended) Use the Issues columns, with "—" where live has no value.
  2. Give each register its own columns (needs a board).

### Batch 4 (lane B, API 1.24.0, D-185)

Parts that 1.24.0 now supplies are switched on as the boards draw them (D-185), with no question. Below is only new behaviour. We build option 1 of each.

- **F-73 · B26. Add a billing contact now.** 1.24.0 lets Setup record a billing contact, but only with a proof already recorded on the project; there is no proof upload from the client page. The form also needs customer, client name and role, which the board does not draw.
  1. (Recommended) Build it now: the form picks one of the project's recorded proofs, adds the extra fields, and is disabled with its reason when there is no proof.
  2. Keep it disabled (as in B6) until a proof can be uploaded from the client page.
- **F-74 · B27. Setup saves as "draft, then review".** 1.24.0 has proof upload, delegation drafts, template replacement and review actions. Company settings open without a project (PSL: "Company-wide settings should be accessible from Setup without needing to know a project first").
  1. (Recommended) Build the saves now: every change is saved as a draft that is never shown as in force, review buttons follow what the server allows, a company selector shows only when you manage more than one company, and Templates keeps a project selector (templates belong to a project). Rule rows stay read-only: none of them matches a rule type the backend can draft yet.
  2. Keep Setup read-only this release.
- **F-76 · B28. Staff invite, deactivate, restore and role changes.** 1.24.0 has these commands, but PSL's answer says who may read staff, not who may change them.
  1. (Recommended) Keep F-76 read-only; build the changes as a separate feature once PSL says who may make them (needs PSL).
  2. Build them now for whoever the server allows.
- **F-79 · B29. Month-end and payments wording.**
  1. (Recommended) "Received this month covers N of M projects; K could not be read." only when some could not be read; OWED shows the known part plus "Unknown" with a count of invoices that have no known balance.
  2. Show the total alone with a "partial" tag.
- **F-71 · B30. Money and Milestones: paid word and proof.** Live gives no paid word on the money read (it lives on each invoice's payments) and no proof file route.
  1. (Recommended) No paid word: show the status as given plus Paid and Owed amounts; a "Proof" button shows the recorded name, date and proof version.
  2. Read each invoice's payments to show Paid / Part paid / Not paid.
- **F-78 · B31 (for PSL). Does marking a milestone complete start the invoice draft?** PSL decided the PMO Lead confirms the milestone. The backend only says a Finance handoff is queued. Mark complete stays BLOCKED until PSL answers.
  1. (Recommended) Completion only queues the Finance handoff; Finance starts the invoice.
  2. Completion starts the invoice draft automatically.

### Batch 5 (lane B)

- **F-78 · B32. Mark a milestone complete: board changes.** Details in `delivery/features/F-78/spec.md` ("Conflicts with the boards"). We build option 1 of each.
  1. (Recommended) Accept all: the board's "Chidi drafts the stage 2 invoice… Finance Lead approves" becomes the D-187 wording (completion queues the Finance handoff; "Completing a milestone is not invoicing it" stays); proof is a choice of the project's recorded proofs, plus a PDF upload when the server allows it, with a "this is the right file" tick; a hold line explains why it can't be marked yet; no recorder name or release reference (live gives neither); the page shows the milestone name before recording and the completed date after; "Mark complete" shows on uncompleted rows only when the server allows it, with one hold line above the table.
  2. Show the milestone's stage number through the link (option 2 of item 4).

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

### LC-Q7 · F-88 · Assigning the PM now needs proof and a reason
The approved Assign PM drawer draws proof as optional and a short optional Note. Live requires both a proof (chosen from the list the backend offers for that RFP) and a written reason (up to 4000 characters), and has no Note field (backend question C-12).
1. **(Recommended)** Make "Proof" a required choice from the offered list and replace Note with a required "Reason for choosing this PM"; drop "(optional)".
2. Keep the drawer as drawn and hold Assign PM until the backend makes both optional.

### LC-Q8 · F-88 · Log RFP: the Note and the client name
The approved Log RFP form has a free Note and a client picked by name. Live stores no note on a received RFP, and the client picker lists only the organisations where you may record a received bid; a new client is typed as a name (backend questions C-9, C-10).
1. **(Recommended)** Remove the Note. Keep the organisation picker (required) and add a plain text "Client name as written in the RFP", optional.
2. Remove the Note and show only the organisation picker.
3. Keep the Note on screen and hold it until the backend stores it.

### LC-Q9 · F-88 · After logging or assigning: what the success words can say
Live returns no work item id after logging and no PM name or "what happens next" after assigning (backend questions C-7, C-13). The drawn success lines name the PM and say the PM is alerted.
1. **(Recommended)** After logging, say "RFP logged" with the reference and received time read back from the receipt and a link to the Unassigned list. After assigning, say "PM assigned" with the person's name from the chosen list entry, only after the list is re-read; leave out the "alerted" and next-steps lines.
2. Keep the drawn sentences and accept that they may not be true.

### LC-Q10 · F-86 · Weekly report start form: what the live body changes from the board
The SCR-04 weekly board draws Project, Week ("Must have ended; up to 8 days") and a Template line reading "Client weekly report · test template v1". The live `POST /work` weekly body also requires a `reference` (1 to 160 characters), carries the template only as an id with no name, and has no "up to 8 days" rule in the contract.
1. **(Recommended)** Add one text field "Reference" under Week, leave the template line out (send `template_id` and `content_id` as null), and drop the "up to 8 days" help line; the server's own message shows if the week is refused.
2. Keep the Template line as drawn and fill the words from a source the live API does not serve yet (needs a backend change).

### LC-Q11 · F-86 · Upload on the weekly form
The weekly board draws no file field and the live weekly body has no field for an uploaded file (`upload_id` has nowhere to go). The first slice still builds the upload for the lines that need it.
1. **(Recommended)** Build the upload box (the F-85 evidence picker) in Start work but show it only on lines whose body takes a file; the weekly form shows none.
2. Show an optional "Add files to this project" box on the weekly form that uploads to the case but is not sent with the start.

### LC-Q12 · F-87 · Resume, Cancel and Check what happened: where they sit
No approved board draws a Resume, Cancel or Pause/Continue button on the work item. The awaiting-reconciliation board draws a "Confirm what happened" panel with choices and proof (replaced by one button under LC-Q2). The live work item lists which of these the person may use.
1. **(Recommended)** One small row of buttons under the header, shown only for what the API lists: "Check what happened" (when `reconcile` is listed), "Resume" and "Cancel" (when listed in `available_control`). Cancel asks for a plain yes/no confirmation first. Same row on the phone, stacked. No new colours or panels.
2. Put "Check what happened" inside the next-step callout and the other two in the page menu.
3. Hold the buttons until the design engineer draws them.

### LC-Q13 · F-87 · Pausing and continuing background work
Live lists `background` as an available action but does not say whether the background work is now running or paused (backend question LC-7). Pause and Continue are the two answers to the one call.
1. **(Recommended)** Show two buttons, "Pause background work" and "Continue background work", whenever `background` is listed. The server's answer decides (it refuses the one that does not apply, and we show its message). No guess from the state.
2. Show only "Pause background work" while the item is processing and nothing otherwise.
3. Hold background controls until the backend serves the current setting.

### LC-Q14 · F-89 · Review buttons on the weekly report
The approved review board draws two buttons, "Approve and send" and "Return with a note". Live also allows a third verdict, reject, and lists which verdicts this person may give (`review_verdicts`).
1. **(Recommended)** Draw a button for each verdict the API lists, in the order Approve and send, Return with a note, Refuse. Return and Refuse need a note. No extra confirm: the board's line "Approving sends this exact version to the client" stays above the buttons.
2. Same, plus a yes/no confirm before Approve, because it reaches the client.
3. Draw only the two board buttons and hold Refuse until the design engineer draws it.

### LC-Q15 · F-89 · Editing after a return
The returned board quotes the reviewer's note and has an "Edit your update" button with no edit screen drawn. Live does not serve the note (backend C-16), requires a "reason" with every correction, and carries cites as record ids with no labels (C-15).
1. **(Recommended)** "Returned to you" with no quote. "Edit your update" opens an inline form: four text boxes prefilled from the report, "N records cited" under each (cites kept as they are, not editable), a required "Reason for the change", then "Send for review" and "Cancel".
2. Hold editing until the backend serves the returned note and cite labels.

### LC-Q16 · F-89 · What the reviewer sees before approving
The review board shows the four parts with their records, a byline and a link to the report as the client will see it. Live gives the reviewer a version id and the list of verdicts; the report text is not documented as served to a reviewer, there is no byline, and the client-facing preview is not connected yet (backend B-7, C-17).
1. **(Recommended by the lane C coordinator)** Do not draw Approve and send until the parts are shown on the page: the reviewer must see what goes to the client. Return and Refuse stay.
2. Show the parts the report read serves (nothing more, no link, no byline) and the review buttons whenever the API offers them. If no text is served, the block says so in one line and Approve is still drawn (the spec writer's first pick; it can let a reviewer approve a client message they cannot read).
3. Hold the whole review block until the preview is connected.

_LC-Q10 onwards were added after batch 1 went out; D-182 covers LC-Q1 to LC-Q9 only. They stay open for batch 2, and lane C builds on their recommended options meanwhile._

### LC-Q17 · F-88 · Assign PM: the two confirmation tick-boxes (API 1.24.0)
Live now lets the person upload a file as the proof for choosing a PM, but only with a "checked" confirmation (`checked: true`) sent beside it. Logging an RFP also has a `context_attested` confirmation of the client name and submission instructions typed on the form. The contract gives no words for either.
1. **(Recommended)** Assign PM, when a file is uploaded: a required tick-box "I have checked this file and it supports my choice." Log RFP: an optional tick-box "I confirm the client name and submission details above match the RFP." shown only when a client name or submission detail is filled in.
2. Show no tick-boxes and send the confirmations as true. (Not recommended: it records a confirmation nobody gave.)
3. Hold both until PSL supplies the wording.

### LC-Q18 · F-89 · Comparing a report with its previous version
API 1.24.0 can compare two versions of the same report (changed, added, removed and unchanged sections, with their records). The weekly report read gives only this version's id, not the previous one, and the SCR-25 boards draw no compare. The page shows the report text and the agent's notes without it.
1. **(Recommended)** Leave compare out of this feature. Ask the backend to add the previous version's id to the weekly report read (one field); then add a "What changed since the last version" view in a small follow-up, drawn by the design engineer first.
2. Build a compare view now with no board, using the id the backend supplies later.

### LC-Q19 · F-87 · Wording of "Confirm what happened"
The approved panel says "It didn't arrive. Allow one resend of the same version." and "I can't tell yet. Keep it held and remind me tomorrow." The backend records an observation (delivered, not delivered, unknown) with a reason and proof, and does not resend, remind, verify or approve anything (A-13, answers section 10). The board also has no Reason box and shows proof only for "It arrived", while live needs both for every outcome.
1. **(Recommended)** Keep the three choices with short plain sublines that promise nothing the backend does not do, add a required Reason box, always show the proof picker, and keep only "Your choice is recorded with your name."
2. Keep the board's wording and ask the backend to add resend and reminders (a new behaviour).
3. Hold the panel until the design engineer redraws it.

### LC-Q20 · F-90 · Release invoice: the button and its confirmation
No SCR-02 board draws a "Release invoice" button. Live lists `release_invoice` in `actions[]` only for a person the server allows, and releasing cannot be undone from the page. The server serves no amount or condition on this call, so none can be shown in a confirmation.
1. **(Recommended)** Add "Release invoice" to the same row of buttons as Check what happened and Resume (LC-Q12), shown only when the API lists it, with a plain yes/no dialog ("Release this invoice?" / "This sends the invoice onward and can't be undone from here." / Release invoice, Keep it). No amount line.
2. Same button with no dialog (one press releases).
3. Hold the button until the design engineer draws it.

### LC-Q21 · F-90 · Invoice details on the work item
The verified and awaiting-reconciliation boards show the invoice through the six facts and numbered steps, which belong to the tracking feature (F-91). API 1.24.0 also serves the invoice itself (reference, version, issued, delivered, amount, paid, owed).
1. **(Recommended)** Add one small read-only "Invoice" block on the work item with those seven values; anything the server leaves empty reads "Unknown" (or "Not issued yet" / "No delivery recorded"), never 0. No payment or correction links (those are the Finance workspaces, lane D).
2. Show nothing until F-91 draws the facts strip, and rely on it.

### LC-Q22 · F-90 · After an uncertain release, does reloading the page unlock the button?
After a timeout the page locks the release until the item changes version or the server stops listing it. The lock lives in the open page, so reloading clears it and the server's own list decides what is offered again. A release is money-moving and the API has no duplicate key.
1. **(Recommended)** Keep the lock across a reload (remembered in the browser for that work item and version) until the item changes version or the server stops listing the action, and say why.
2. Let a reload clear the lock (as for the other work item buttons, F-87); the server still refuses a stale version.

### LC-Q23 · F-91 · History on 1.24.0: counts, version and "Restricted" marks
The history boards show a count on each filter, a version column and "Restricted" entries. The API serves actor kind, station, status, time, reason and a paging cursor only.
1. **(Recommended)** Leave out the counts, the version column and the Restricted marks. Keep the filters, the person/agent tag and an "Older events" button.
2. Keep the version column showing "Not recorded".
3. Hold the history change until the backend adds the three.

### LC-Q24 · F-91 · The agent card on the work item
The boards draw the agent's picture and name and a numbered list of steps with the record each read. The API gives one activity line (and the agent's name, and a last-activity summary).
1. **(Recommended by the lane C coordinator, per D-185)** Draw the agent card as the board does with what the API serves: the agent's name (`item.agent`) and picture by that name, the activity line (or progress with its time) and the last-activity summary (`tracking.last_activity`). Leave out only the numbered steps, which nothing serves.
2. Show the one activity line (or progress with its time) and nothing else (the spec writer's first pick; it hides served data, against D-185).

### LC-Q25 · F-91 · Words in the station track and facts strip
The boards write a detail in each station and a date in each earned fact. The API gives each station's holder name, "unassigned" for a future station, and a time only for Verified. It does not say whether a holder is a person or an agent.
1. **(Recommended)** Station detail is the holder's name ("Unassigned" for a future station, "Not recorded" if none was recorded); the colour of the current station follows the station and the item's state. Only Verified shows a time.
2. Same, but every current station is drawn in one neutral colour (no person/agent distinction).
3. Hold the track until the backend says whether a holder is a person or an agent.

### LC-Q26 · F-91 · Amount and invoice version in the work item header
The boards' header shows the amount and invoice version. The tracking read has neither; the amount is on the invoice or Finance panel (F-90).
1. **(Recommended)** Leave them out of the header; add reference, who started it and when to the sub-line. The amount appears only where F-90 draws the invoice block.
2. Show "Amount: see invoice" with a link to the invoice block.

### LC-Q27 · F-93 · Confirm what happened: more than one send, and what shows after recording
The approved panel draws one set of choices and no "after" state. Live can list more than one uncertain send for the same item, and after recording the backend only returns the saved choice and its time.
1. **(Recommended)** Draw one panel per uncertain send, headed by its plain job name (never the job number); after recording, replace that panel's inputs with "Recorded: It arrived, 23 Nov 14:05." (the choice and time from the API), with the reason for any disabled button written beside it. Say nothing about resending, reminders or checking.
2. Show only the first uncertain send. (Not recommended: it hides a send nobody has settled.)
3. Hold the panel until the design engineer draws these states.

### LC-Q28 · F-92 · Start forms for minutes, issue, change, emergency and escalation: what the live body changes from the boards
The SCR-04 boards draw minutes (Project, Meeting, Audience, Proof), change (Project, "What the client asked for", Proof), incident (Project, Incident, Plan) and escalation (Project, From issue, Escalate to). The live bodies take chosen records instead: minutes needs a Template and a Reference and takes the notes file; change takes a Change version, Authorisation, Template and Reference; emergency takes an Emergency record, Authorisation, Outcome, Template, Audience and Reference; escalation takes an Escalation request (direction and target are already on it), Template and Reference. There is no long-text box in any of them. The issue form matches its board.
1. **(Recommended)** Build the live fields and leave the boards' long-text boxes and "Escalate to" out; labels come from the field names and the design engineer edits the words.
2. Ask the backend to accept the boards' fields (a new behaviour).
3. Hold these four lines until the design engineer redraws the boards.

### LC-Q29 · F-92 · Leadership report start is not the weekly shape
Readiness said the leadership report body matches the weekly report. In API 1.24.0 it also needs a report kind (Tuesday or monthly), an audience and six lists of chosen records (meetings, actions, milestones, issues, changes, escalations) read from `leadership-report-intake`, not from the usual source list.
1. **(Recommended)** Leave the leadership report out of batch 1; it shows as "Not available here yet" with its link, and gets its own feature and board check.
2. Build it now with the six record lists and no board.
3. Send empty lists (not recommended: the server may refuse and the board draws no such form).

### LC-Q30 · F-92 · Minutes: start from a notes file
`GET /lines` says minutes start with a JSON `POST /work` that needs an existing evidence id, but the live API also has `POST /projects/{case_id}/minutes/intake`, which takes the notes file directly (the route the minutes board's Proof box implies).
1. **(Recommended)** Use the notes-file route; ask the backend to serve it as the line's submit address.
2. Use `POST /work` and pick an already-filed meeting-notes record (no upload; the board's Proof box has no live meaning).
3. Offer both.

### LC-Q31 · F-92 · Uploads and organisation picker have no use in batch 1
None of the five bodies takes an `upload_id` or names an organisation list, and an upload id cannot stand in for an evidence id. The spec builds no upload-id field or organisation picker here; the organisation picker stays with F-88's received bid, and the escalation request list comes from the project's register read.
1. **(Recommended)** Accept: the engine has the slots; later lines add controls when a body needs them.
2. Add an optional "Add files to this project" box to every form (no live field takes it).

## Lane D

### LD-Q1 · F-107 · Business-unit totals (SCR-57): build on what the API discloses?
F-44 was held on D-PAYROLL-VISIBILITY: may Finance, the BU reviewer and Chidi see staff count and staff cost per business unit? That decision is still open in `architecture/model.json`. PSL's 23 Nov answers (E-26, E-27, E-30, E-32 in `backend-answers.md`) now have the backend enforce it per person: totals come from the eligible payroll match, a recipient gets the approved BU totals only (no staff counts, no names, no pay rows), a too-small group holds the publication, and approval is an independent review (kind `business_unit`).
1. **(Recommended)** Build SCR-57 on what the API serves to each person and nothing more. A board figure the API does not give that person (for example "Legal (2 people)" for a recipient) is hidden. The merge comes to you in the merge batch, because it shows restricted payroll totals and sends them to the CEO and BU heads.
2. Keep F-107 blocked until PSL records D-PAYROLL-VISIBILITY itself.

_Context added later: `architecture/model.json` scopes D-PAYROLL-VISIBILITY to "SCR-13 fields; E-SETUP-RULES area payroll_visibility", the Setup field-visibility editor. Lane D's payroll readiness checks (F-108, F-109, F-110) found that it does not gate those screens, because the backend enforces restricted payroll per person (INV-RESTRICTED). Lane D builds the payroll screens on that reading. Their merges come to you in the merge batch._

### LD-Q2 · All lane D specs below · Accept every recommended option?
Each lane D spec lists its own board conflicts and presentation questions, with the options and the recommendation first, under "Questions" in its `spec.md`. Most questions are the same few patterns: hide a part the API does not supply (D-182), add a proof or evidence select the live command needs (PSL answer 1), add a required reason, or say where a board-less control sits. Lane D builds on the recommended options meanwhile.
1. **(Recommended)** Accept every recommended option in the lane D specs listed below ("accept all recs", as in D-182 and D-183). Lane D merges the routine ones under D-184 and brings the money, payroll and client-facing ones to you in the merge batch.
2. Accept all, except the ones you name.
3. Go through them one feature at a time.

- **F-100 · Payment reminder (SCR-32)**, 4 questions, `delivery/features/F-100/spec.md`:
   1. Where should `mode` and the scheduled send time appear, given the boards do not draw them?
   2. The boards draw "Copy:
   3. The boards show one fixed "Send reminder / Edit / Not now" row.
   4. "Not now" needs a reason (API requires 1..1000 chars) and the boards draw no reason field.
- **F-101 · Income schedules, part 1 (SCR-54)**, 5 questions, `delivery/features/F-101/spec.md`:
   1. Evidence on the review form (boards draw only a Note).
   2. The reviewer's note on a returned schedule (board quotes it; the read has no text field).
   3. Note on Approve (the board shows the note needed only for return and reject).
   4. Wording for the two hold codes (the board draws "Who reviews schedules:
   5. Withdraw approval is offered whenever the read lists `revoke`, which the board draws only on the withdrawn state.
- **F-102 · Fixed assets, part 1 (SCR-55)**, 5 questions, `delivery/features/F-102/spec.md`:
   1. Where to put `completeness` and `native_source_verified`, which no board draws.
   2. The verified board draws "Register review APPROVED 13 NOV", "Date review", "Schedule review" and "Feeds MANAGEMENT ACCOUNTS".
   3. The investigating and calculating boards draw an agent card ("step 3 of 4", sources) and the calculating board draws "Rule F07 CALCULATION RULES".
   4. Phone boards drop desktop content (investigating has no Register facts; calculating shows only "PROCESSING").
   5. The schedule table has per-row `findings[]` and a held reason that no board draws.
- **F-103 · Cash forecast, part 1 (SCR-56)**, 4 questions, `delivery/features/F-103/spec.md`:
   1. **The uncertain delivery state:
   2. **Actuals "more" flags have no paging route.** `more_actuals`, `more_history`, `more_notes` say a list is cut, but the route takes no cursor or limit.
   3. **Write controls drawn on the read boards (review Decide panel, group-rows editing, "Record what happened", "Record actuals").** The boards draw them on the same artbo…
   4. **Board parts the API cannot fill (listed for the design engineer).** (a) "Reviewer not set" warning:
- **F-104 · Ledger source, part 1 (SCR-58)**, 8 questions, `delivery/features/F-104/spec.md`:
   1. Parts the boards draw that API 1.24.0 does not supply:
   2. The observe board shows "Found" already chosen and a proof "qb-screenshot-je7741.png · Uploaded · 310 KB".
   3. The review board's note label reads "(needed to return, reject or withdraw)" and offers no reason for approve.
   4. The verdict needs one evidence item the boards never draw, and the API lists them in `review_evidence[]` without saying how a reviewer makes one.
   5. The rejected board's "Correct" button and "Correct it with the right evidence; the correction continues the same lineage", and the "re-check reopens it" sentence on ve…
   6. The observation proof is optional on the JSON route but required on the board.
   7. No SCR-58 board draws capturing the ledger source (`incumbent-evidence` kind `ledger_source`) or starting the line (`POST /work`, `finance-ledger/v1`).
   8. The four answers are drawn as a row of segments on the board; the shared field rule draws more than three options as a `Select`.
- **F-105 · Management accounts intake (SCR-53)**, 6 questions, `delivery/features/F-105/spec.md`:
   1. Investigating board:
   2. Returned board:
   3. Owner-needed board:
   4. Units board:
   5. Intake page entry point:
   6. Board "Upload a corrected file" on the held board also says "or change the declared period or currency if the file is right".
- **F-106 · Management accounts reviews and publication (SCR-53)**, 6 questions, `delivery/features/F-106/spec.md`:
   1. The live decision requires an evidence id, and the reviews board has no evidence field.
   2. How should the router tell drafting from investigating, since both can be `processing`?
   3. Uncertain board action.
   4. Recipients on publishing and verified.
   5. Verified review tile.
   6. Reassess has no board.
- **F-109 · Payroll corrections (SCR-37, restricted)**, 4 questions, `delivery/features/F-109/spec.md`:
   1. Note field and story text.
   2. Waiting count, filter and decided row.
   3. Finance receipt section is not drawn, and the board's header says Finance never sees these records.
   4. Proof chooser.
- **F-111 · Issue, part 1 reads (SCR-30)**, 4 questions, `delivery/features/F-111/spec.md`:
   1. Status wording.
   2. Disabled write controls.
   3. No-owner detection.
   4. Board parts the spec removes or changes (design engineer decides once):
- **F-112 · Change request, part 1 (SCR-31)**, 8 questions, `delivery/features/F-112/spec.md`:
   1. The "Log a new change" form and the Changes list have no board, and the readiness scope requires them.
   2. Where the change list lives.
   3. The default board draws only Product, Client and Engineering Lead and the decision board draws all five with the line "Open question for the backend team:
   4. Impact board versus contract:
   5. Authorise board draws "Authorised by", "Authorised on" and a proof upload.
   6. Rejected board says "The change is closed as rejected" and quotes the client's note and who recorded it.
   7. Page frame:
   8. Mobile boards for the four wide parts (impact table, five-step track):
- **F-113 · Delivery overview (SCR-43)**, 5 questions, `delivery/features/F-113/spec.md`:
   1. Tab bar entry.
   2. Row order.
   3. Board parts hidden because the API gives nothing (recommend hide, as D-182):
   4. Row state wording.
   5. The board sentence "Hypercare, archive and handover run side by side after go-live.
- **F-114 · Go-live acceptance, part 1 (SCR-45)**, 5 questions, `delivery/features/F-114/spec.md`:
   1. **Where does the client reply's proof come from?** (a) Use F-85's file-to-evidence proposal and hold the write if it yields nothing (recommended; matches Assumption 1).
   2. **"Ask Tola to draft v2" (board -changes).** (a) Show "Prepare v2" with a reason box and no agent wording (recommended, D-182).
   3. **One form versus two on the board.** The board draws one "What the client did:
   4. **Signer source fields have no board.** The API needs source system, reference, decision id, decision version, signer reference and signed time for each signer.
   5. **Link from the work item page.** (a) A single "Open go-live acceptance" link on `/work/{id}` for panel keys `go-live-signoff` and `go-live-replies`, added as a small…
- **F-115 · Hypercare, part 1 (SCR-46)**, 6 questions, `delivery/features/F-115/spec.md`:
   1. Open issues link.
   2. Day count.
   3. Observation rows.
   4. Tola's card and "Ask Tola".
   5. Pause control.
   6. Frame section kinds.
- **F-116 · Archive (SCR-47)**, 5 questions, `delivery/features/F-116/spec.md`:
   1. **Human delivery observation for an unconfirmed file.** `POST /work/{id}/delivery-observations` needs `effect {job_id, job_type}`, a work-bound `proof_id` and a reason…
   2. **Board wording that no longer holds.** The working board says "Archiving has no approval step.
   3. **Which panel key and route.** Whether `GET /work/{id}` lists an archive panel key in 1.24.0 is unconfirmed.
   4. **Start control placement.** No board draws the source list or the Start button (the boards start with Tola already working).
   5. **Per-file checks on 390.** Six or more unknown files with two buttons each are long on mobile.
- **F-117 · Handover to Support (SCR-48)**, 5 questions, `delivery/features/F-117/spec.md`:
   1. **Proof for Support's reply.** `evidence_id` must be an existing record, and no documented call turns an uploaded file into one for this route (D-1 says use the owning…
   2. **Fields the boards do not draw.** The live record needs Role, How they replied (channel), Who replied as text and a required Note; the record board draws one "Support…
   3. **"Ask Tola to draft v2".** Live `corrections` needs a typed `reason` and the three source ids; the board has one button.
   4. **Which panel key and route.** The F-85 page draws panels from `panels[]`; whether `GET /work/{id}` lists a handover panel key for this line in 1.24.0 is unconfirmed i…
   5. **Gap rows after v2.** Live gives no per-gap status, so "OPEN" is drawn while the latest record still has gaps and no row ever shows closed.
- **F-118 · Closure (SCR-49)**, 7 questions, `delivery/features/F-118/spec.md`:
   1. Where do `version_id` and `evidence_id` for the closure decision come from on a read?
   2. Check titles:
   3. The "blocked" state maps `ready_to_prepare:false` with no work; "ready, not started" has no board.
   4. Role word on the decision board:
   5. Returned state:
   6. Finance evidence field:
   7. Source corrections for the closure line (`POST /work/{id}/corrections`):
- **F-108 · Payroll import and matching (SCR-09, SCR-18, restricted)**, 5 questions, `delivery/features/F-108/spec.md`:
   1. SCR-18 permission board:
   2. SCR-09 error board:
   3. SCR-18 default board:
   4. The board's SCR-18 default view is titled for HR roles with a top-bar persona "HR Lead" and "Ask Zainab a question" / "Review the 4 problems" buttons.
   5. Presentation:
- **F-110 · Payroll run, part 1 (SCR-59, restricted)**, 7 questions, `delivery/features/F-110/spec.md`:
   1. Per-recipient receipts (boards receipts, verified, followup draw "Finance Lead RECEIVED / CEO WAITING" and "2 of 2").
   2. The nine-station strip on every board.
   3. F-108 also lists `working` and `receive_hr` for SCR-18.
   4. Where payroll runs start (`POST /work` `finance-payroll/v1`, requires request and input ids from F-108).
   5. Per-input state words (Needs you, Approved, Received) and the "See the problem rows" link.
   6. The `payroll-recovery` prior receipt has a board slot (followup "Already delivered") but with names and dates per recipient.
   7. The "Gross pay ₦...
- **F-119 · Retrospective (SCR-33)**, 5 questions, `delivery/features/F-119/spec.md`:
   1. Decisions rows (not on the board).
   2. "When it was held" (not on the board).
   3. Notes file source.
   4. Footnote wording "PMO Lead decides on".
   5. Where the checklist strip sits when there is no `dossier` in the link.

### LD-Q3 · F-107 · BU totals part 1 (SCR-57): five presentation questions
Added after batch 3. The full options are under "Questions" in `delivery/features/F-107/spec.md`. Lane D builds on the recommended options meanwhile.
1. Staff column: the API types `totals` as a free key-to-value map. **(Recommended)** Draw the Staff column only when the API serves that person a staff count, otherwise hide it.
2. Decision note: `/reviews` for `business_unit` has no note field. **(Recommended)** Remove the note box and label the button "Return".
3. "Withdraw approval": the API accepts `revoke` but does not say whether an approval exists. **(Recommended)** Draw it as the board does and show the server's refusal as given.
4. `restart` and `prepare_rule` have no board and need a configuration id that no read serves. **(Recommended)** No form in part 1.
5. Hide the board figures the API does not serve (staff in the match, BU counts, "Legal (2 people)", owner names, the station track, "Ask Chidi"), as D-182 and D-187 do. **(Recommended)** Hide each.

### LD-Q4 · Part 2 specs · Plain forms where no board is drawn, and accept every recommended option?
The part 2 specs add the write forms the live commands need: evidence choices, reasons, confirm steps, retry and cancel, the go-live milestone confirmation, and the BU and payroll publish and receipt. Most of these have no board. Several spec writers suggest drawing boards first (the four-concepts rule).
1. **(Recommended)** Build them now as plain forms from existing components, in the same pattern D-187 accepted for part 1, and accept every recommended option in the part 2 specs below. You check the merged screens on port 3000, and anything you redraw becomes a fix. Money, payroll, BU totals and client-facing ones still come to you in the merge batch.
2. Draw boards first (four concepts each) for the undrawn forms. Those part 2 features wait until the boards exist.
3. Accept all recommended options except the ones you name.
F-114C (go-live document review) is held: no read gives the reviewer the version (backend LD-6). New backend questions LD-4 to LD-11 are in `backend-questions.md`.

- **F-101B · Income schedules, part 2**, 5 questions, `delivery/features/F-101B/spec.md`:
   1. The adjustment review form (`POST /projects/{case_id}/accounting-adjustments/{adjustment_id}` needs `role`, a 1 to 50 character string; no read says which ro…
   2. Source mappings (`POST .../accounting-sources/{source_id}/mappings`, `GET .../accounting-mappings/{mapping_id}`).
   3. Combined export (Conflict 1).
   4. Partial duplicate settlement.
   5. Where the adjustment page lives.
- **F-102B · Fixed assets, part 2**, 4 questions, `delivery/features/F-102B/spec.md`:
   1. The review form shows the basis review as a further choice beside register and schedule, only when `review_options` lists it.
   2. One shared evidence picker (a select labelled by kind and version) for the review, capture and dates forms.
   3. Phone shows the same forms in one column, as F-102.
   4. F-87's `useWorkCommand` may be JSON-only.
- **F-103B · Cash forecast, part 2**, 4 questions, `delivery/features/F-103B/spec.md`:
   1. **Where does the evidence for a verdict, a record-actual and a match come from?** The forecast read lists none and those routes have no upload field.
   2. **Withdraw, post and restart.** Readiness lists withdraw and post, but the 1.25.0 `POST /forecast` union has no such action; `lifecycle` `restart` needs a `c…
   3. **Who reviews and publishes a group forecast?** `POST disclosure` requires `reviewer_roles`, `publisher_roles` and `allow_preparer_review`, and the board say…
   4. **Confirm steps.** Retry and cancel of a delivery are hard to undo.
- **F-104B · Ledger source, part 2**, 6 questions, `delivery/features/F-104B/spec.md`:
   1. Restart needs the work item's `state` and the page's `LineContext` does not carry it.
   2. The rejected board's "Correct" button.
   3. Plain-words labels for the two modes, which no board draws:
   4. Backend:
   5. Who types the "Reference" value.
   6. The ticked list is every claim the person can see (up to 100), not only related ones.
- **F-107B · BU totals, part 2 (restricted)**, 4 questions, `delivery/features/F-107B/spec.md`:
   1. Receipt progress for Finance.
   2. Cancel-after-publish.
   3. A Finance reader who is also a recipient.
   4. Live proof of the publish.
- **F-110B · Payroll run, part 2 (restricted)**, 5 questions, `delivery/features/F-110B/spec.md`:
   1. Where does the evidence id for a payroll review come from?
   2. The same gap for Withdraw (`evidence_id` required, no list, no proof route).
   3. What does "Ask HR to correct" mean to the API?
   4. Does a board draw the successor entry (Replace these totals) and the "Start a corrected run" entry?
   5. Review verdicts "Revoke approval" and "Approve draft match":
- **F-111B · Issue, part 2 writes**, 3 questions, `delivery/features/F-111B/spec.md`:
   1. Message panel without a board (design engineer).
   2. Set an owner on the no-owner board.
   3. Verified/closed issues.
- **F-112B · Change request, part 2**, 5 questions, `delivery/features/F-112B/spec.md`:
   1. The close form and the document review controls have no board.
   2. Execution evidence:
   3. The closed board's "Milestone 3's scope now includes" line and "Open milestones" link depend on `change-milestone-link`, which has no board.
   4. `close` source fields (D-7) are typed by the PM from the retained proof.
   5. "Cancel" appears on every job not clearly finished (Assumption 4).
- **F-113B · Release gates (SCR-44)**, 4 questions, `delivery/features/F-113B/spec.md`:
   1. Resolved by the coordinator:
   2. Resolved by PSL answer 1:
   3. How should the blocker issue link read?
   4. Reject is in `verdicts[]` but not on the board.
- **F-114B · Go-live, part 2 milestone**, 4 questions, `delivery/features/F-114B/spec.md`:
   1. **Who supplies the milestone name when `milestone.name` is null?** (a) The PMO Lead types it, no prefill (recommended; matches D-17 and the required `name`).
   2. **Where does a corrected or withdrawn reply's proof come from?** (a) Same as F-114's question 1:
   3. **Should withdrawal ask for all reply fields?** (a) Yes, as the contract requires (recommended).
   4. **Hypercare pointer after completion.** (a) Say nothing (recommended, nothing supplied).
- **F-115B · Hypercare, part 2**, 3 questions, `delivery/features/F-115B/spec.md`:
   1. Criteria `issue_clearance`.
   2. Criteria form board.
   3. Observation proof when no file is on the project.

## Answers, batch 1 (23 Nov 2026, D-182)

Every recommended option above is accepted ("Hide, accept all recs"), including LC-Q1 (hide until backend), F-65 (as recommended) and F-76 (read-only list now). Lanes: unpark these features and build them as their specs recommend.

## Answers, batch 2 (23 Nov 2026, D-183)

F-58: accepted, merge approved. All recommended options accepted for F-59 Q1 to Q7, B18, LC-Q10 to LC-Q16 (LC-Q16 "Hold Approve", the recommendation), and LC-Q14 "Add Refuse".

## Answers, batch 3 (23 Nov 2026, D-187)

Every recommended option is accepted: lane A 1.24.0 questions, B19 to B30, LC-Q17 to LC-Q22, and all lane D specs (LD-Q2). LD-Q1: build SCR-57 on what the API serves; the merge goes to the design engineer. B31: completion only queues the Finance handoff; Finance starts the invoice.
