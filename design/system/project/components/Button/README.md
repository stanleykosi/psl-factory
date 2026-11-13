# Button

Buttons do one thing each, and their colour says which kind of thing.

## Kinds
- **Primary** (`action` blue): the main action on a screen that is not starting work — Approve, Ask, Save, Send to review.
- **Start** (`signal` orange): starting a line of work, and the one action a person must take at the current station (Log change, Start work). At most one per screen.
- **Confirm** (`verified` green): recording that something is verified or complete (Mark verified, Accept handover).
- **Dark** (`ink`): recording a response or fact on someone else's behalf (Record response, Record payment).
- **Secondary** (outline): Return, Cancel, Back, Edit, and any second choice beside a filled button.
- **Reject** (outline in `signal-ink`): Reject, Remove, Deactivate. Never filled: a destructive action is never the loudest thing on the screen.
- **Text**: low-weight actions inside sentences and toolbars (Change line, Clear all, Undo).

## States
Default, Hover (one step darker: `*-strong`), Pressed (`*-ink`), Focus (2px `focus` ring, 2px gap), Disabled (`disabled` fill, `ink-muted` text, with the reason written next to it), Busy (three squares fill in turn and the label says what is happening, e.g. "Recording…"; the button stays the same width and cannot be pressed twice).

## Sizes
`control-sm` 40px (top bar and dense toolbars only), `control-md` 44px (default on desktop), `control-lg` 50px (drawer and decision footers), `control-xl` 54px (phone footers, full width).

## Rules
- A label never wraps onto two lines (`white-space: nowrap`); if it does not fit, shorten the label.
- Say what the action does in words: "Approve v3", not "OK". Pair a decision button with a line saying what it does not do ("Approving does not send the invoice").
- A disabled button always has its reason beside it ("Add the proof file to record"). Prefer an enabled button that explains what is missing when pressed.
- Agents never get an Approve, Send or Pay button.

## Consumer provides
The label, the kind class (`psl-btn--start` etc.), the size class, and `disabled`/`aria-busy` when needed. Use `<a class="psl-btn">` only for navigation.
