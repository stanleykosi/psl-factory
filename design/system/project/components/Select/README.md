# Select

Pick one value from a list of up to about 15. For longer lists add a search box at the top of the list; for 2 to 5 short options use the segmented choice instead.

## Control
Same box as a text field with a chevron on the right. States: placeholder, hover, focus, open (focus ring stays, chevron turns), chosen, error, disabled.

## List
- Opens below the control (above it if there is no room), at least as wide as the control, with the `shadow-pop` hard shadow.
- Options are 40px tall, with an optional second line in `small`. Group labels in mono caps.
- Option states: default, hover (`steel`), keyboard-active (focus outline), selected (tick and bold), disabled (`ink-subtle`, with the reason as its second line).
- Keyboard: arrow keys move, Enter chooses, Esc closes and returns focus to the control, typing jumps to the first match.
- People are listed as "Name · role", never by email.
