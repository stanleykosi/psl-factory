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
  - `action` (blue) is for buttons and links, and for everything agents do: agent panels use `action-tint` with an `action` border.
  - `verified` (green) is for verified outputs.
  - `waiting` (amber) is for waiting and for sample labels.
  - Every state is also written in words, so colour is never the only signal.
- **Facts strip:** earned facts are `ink` with `on-strong` text; the current one is `signal-tint` with `signal-ink` text; facts not yet earned are `surface` with `ink-muted` text.
- **Type:**
  - `display` (Archivo, expanded) is for screen titles and station names.
  - `sans` (IBM Plex Sans) is for all reading text.
  - `mono` (IBM Plex Mono) is for references, times, amounts and uppercase labels at 0.06em tracking.
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

- Stroke icons, 2px with square caps, drawn on a 20px grid in `ink`.
- Stations are squares and agents are marked with a square badge; people get round avatars.
- No emoji, no illustrations inside working screens.

## Using it

- Load the three Google Fonts families (Archivo with width axis, IBM Plex Sans, IBM Plex Mono).
- Build screens from these tokens only.
- The Next.js frontend in `frontend/` reads `tokens.json` to generate its CSS variables.
