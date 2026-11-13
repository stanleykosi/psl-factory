# TextField

One-line text input with its label always visible above it.

- Label above (`body-strong`), optional fields say "(optional)"; required fields carry no asterisk because most fields are required.
- Hint below in `ink-muted` 13px; an error replaces the hint, in `signal-ink` with a warning icon, and the border turns `signal`.
- Height `control-md` (44px) on desktop, `control-phone` (48px) and 15px text on phones.
- States: empty with placeholder, hover (`surface-subtle`), focus (2px `focus` ring), filled, error, disabled (`steel` ground, `disabled` border), read-only (no outline, `rule-soft` border, for values the factory set).
- The placeholder is an example, never the label. Unknown values are written "Unknown", never left blank or 0.
