# PSL Factory

The design system for PSL's operations factory, from concept C, Assembly line. Every screen is organised around the line a piece of work travels and the separate facts it has earned, so nobody mistakes a draft for an approval.

## Content fundamentals

- Write in plain business language. Name records the way PSL staff do: invoice, SOW, plan, milestone, go-live report. Keep technical references (INV-0412) secondary, in `mono`.
- Use the factory's own state words exactly: Ready to continue, Processing, Waiting, Awaiting Finance decision, Owner needed, Setup needed, Action needed, Effect uncertain, Awaiting reconciliation, Verified, Cancellation requested, Cancelled. Never invent synonyms such as "Done" or "Complete" for a state.
- Facts are never merged. Drafted, reviewed, approved, sent, receipt recorded and verified each get their own word and their own box; paid is a Finance fact and always sits apart.
- Say what an action does not do: "Approving does not send the invoice."
- Unknown is written "Unknown", never 0, never blank.
- Agents prepare and explain; they never "decide", "approve" or "send". Write "The Finance evidence agent drafted v2", not "The system approved".
- Sample, test and mock content always carries a label: SAMPLE DATA, TEST TEMPLATE, MOCK DELIVERY.

## Visual foundations

- **The line is the structure.** Panels and tables sit on `steel` in `surface` boxes bounded by a `rule-strong` (2px) border in `ink`. Corners are `radius-none`; buttons and tags take `radius-sm`.
- **Colour has one job each.**
  - `signal` (PSL orange) means "a person must act here": the current station, the decision panel's header, Start work and the navigation underline.
  - `action` (blue) is for buttons and links, and for everything agents do: agent panels use `action-tint` with an `action` border. A blue tag always means agent or processing work.
  - `verified` (green) is for verified outputs.
  - `waiting` (amber) is for waiting on someone else (the client, an approver, a team) and for sample or test labels.
  - `neutral` (grey) is for tags that are closed, not applicable or just information: Cancelled, Out of scope, Not yet, people and role labels. Priority is a neutral tag with a small mono marker (■■■ high, ■■□ medium, ■□□ low), never a status colour.
  - Tags use only these five families; a state has exactly one colour everywhere.
  - Every state is also written in words, so colour is never the only signal.
- **Facts strip:** earned facts are `ink` with `on-strong` text; the current one is `signal-tint` with `signal-ink` text; facts not yet earned are `surface` with `ink-muted` text.
- **Type:**
  - `display` (Archivo, expanded) is for screen titles and station names.
  - `sans` (IBM Plex Sans) is for all reading text.
  - `mono` (IBM Plex Mono) is for references, times, amounts and uppercase labels at 0.06em tracking.
- **Interaction states** are the same on every control:
  - **Hover:** filled buttons go one step darker (`action-strong`, `signal-strong`, `verified-strong`, `ink-strong`); outline controls, rows and options take `steel` or `surface-subtle`.
  - **Pressed:** filled buttons take their `-ink` colour (`action-ink`, `signal-ink`, `verified-ink`, `ink-pressed`); outline buttons take `neutral-tint`.
  - **Focus:** a 2px solid `focus` ring with a 2px gap on light grounds; `focus-on-strong` (white) on ink, orange and blue fills. Inside joined controls (tabs, segmented options) the ring sits inset. Never remove it.
  - **Disabled:** `disabled` fill or border, `ink-muted` text, and the reason written next to it. Prefer an enabled control that explains what is missing.
  - **Busy:** three small squares fill in turn and the label says what is happening ("Recording…"); the control keeps its width and cannot be pressed twice.
  - **Error:** `signal` border on the field and a `signal-ink` message with a warning icon under it; a validation summary at the top of the form links to each field.
- **Sizes:** `control-md` (44px) is the default height of buttons, inputs and tabs; `control-sm` (40px) only in the top bar and dense toolbars; `control-phone` (48px) for phone inputs; `control-lg` (50px) for drawer and decision footers; `control-xl` (54px) for the full-width phone action.
- **Elevation:** panels on the page never cast a shadow. Floating surfaces (menus, select lists, filter panels, date pickers, dialogs) use `shadow-pop`, a hard 6px offset in `ink`; toasts use `shadow-float`. Drawers, sheets and dialogs dim the page with `scrim`.
- **Layout:** below `bp-phone` (720px) the top bar becomes the phone bar, rows stack, filters move to a bottom sheet and the main action goes full width in a footer; page content is at most 1320px wide.
- **Text styles:** `page-title` for page titles, `drawer-title` for drawers and dialogs, `panel-head` (uppercase) for panel headers, `body` for reading text (`body-phone` on phones), `hint` for hints, errors and what-it-does-not-do lines, `tag` for state tags, `eyebrow` and `label` in mono caps, `amount` and `reference` in mono.
- **Dates and amounts:** dates read "17 Nov 2026", times "14:30 WAT" in mono; amounts are mono with ₦ and two decimals, right-aligned in tables; Unknown is the amber Unknown tag.
- **Spacing:** a 4px base. Panels use `space-4`, sections `space-5`, desktop page gutters `space-6`. Every touch target is at least `space-7` (44px).
- **Contrast:** the signal orange is #C8401C, deepened from concept C's #D8461F, which was 4.4:1 with white text. Every text pair in this system meets 4.5:1.

## Motion

- Motion explains a change of state; it never decorates.
- **Station changes:** a work item's token slides to the next station and the fact it earned fills in, over 240–320ms with an ease-out curve (GSAP in the build).
- **Factory floor:** in the 3D/WebGL overview (three.js), work moves along each line as tokens between square stations.
- **Reduced motion:** for people who have turned motion down, the floor shows counts without movement, and state changes cross-fade in 120ms.
- Dense working screens (queue, decisions, Finance tables) do not animate content while people read.

## Mascots

The department agents have faces. People keep their own photo or initials, so agent work can never be mistaken for a person's decision.

| Mascot | Agent | Colour | Personality | Props |
|---|---|---|---|---|
| **Tola** | PMO agent | `mascot-tola` | Organised, upbeat, keeps work moving | Clipboard, milestone flag |
| **Chidi** | Finance agent | `mascot-chidi` | Calm, precise, trustworthy | Glasses, ledger with receipt |
| **Zainab** | HR agent | `mascot-zainab` | Warm, discreet, guards private data | Lanyard, folder with a lock |

- **Poses and states:** each agent has five poses, mapped to what it is doing.
  - **Idle:** on screen, nothing running.
  - **Working:** reading records or drafting.
  - **Waiting:** needs your answer.
  - **Done:** a draft is ready.
  - **Can't:** no access, or not allowed.
  - Zainab's folder-to-chest pose is her privacy refusal.
- **Where they appear:** the assistant page (the full figure above an empty chat box, avatars in the thread), agent work panels (avatar beside the steps), empty states, and WhatsApp and email alerts (avatar only).
- **Where they never appear:** inside dense tables, on decision buttons, or next to an approval, amount or signature, where a person's decision is shown.
- **Naming:** use the name with the role on first mention ("Tola · PMO agent"), then the name alone.
  - Say "Chidi drafted invoice v2", never "Chidi approved it".
  - Agents draft, read, check and explain; only people approve, send or pay.
- **Colour rule:** mascot colours are identity only. A mascot colour never signals a state, and state colours never stand in for a mascot.
- **Files:** transparent PNGs in `design/mascots/` in the repo, and avatars plus idle poses in this system's Mascots asset group. Final production exports at 2× will replace the current cut-outs.
- **Motion:** in the build, poses change with a short cross-fade (GSAP). For people who have turned motion down, the pose swaps with no animation.

## Iconography

- Stroke icons, 2px with square caps, drawn at 18px on a 20px grid in `ink` or the surrounding text colour. The set is in the Icon component: plus, chevrons, back, search, filter, close, check, warning, info, success, calendar, paperclip, upload, more, menu, send, document, lock, external, sort, down, bell.
- Icons support words and never replace them, except on icon buttons, which always carry an `aria-label`.
- No emoji anywhere in the product: the paperclip icon replaces 📎.
- Stations are squares and agents are marked with a square badge; people get round avatars.
- No emoji, no illustrations inside working screens.

## Using it

- Load the three Google Fonts families (Archivo with width axis, IBM Plex Sans, IBM Plex Mono).
- Build screens from these tokens only, and from the component classes in `components/bundle.css` (`psl-btn`, `psl-input`, `psl-tag`, …) inside an element with the `psl` class. Each component's page shows every state and says what the consumer provides.
- The `is-hover`, `is-pressed`, `is-focus`, `is-open` and `is-disabled` classes exist to show a state in a specification; product screens rely on the real `:hover`, `:active`, `:focus-visible` and `disabled`.
- The Next.js frontend in `frontend/` reads `tokens.json` to generate its CSS variables.
