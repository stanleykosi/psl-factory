# DateField

Dates are written day, short month, year: **17 Nov 2026**. Times are 24-hour in mono (14:30 WAT).

- People can type a date or pick it from the calendar. Typing accepts 17/11/2026 and 17 Nov 2026.
- The calendar marks today with an outline, the chosen day filled `ink`, and days that are not allowed struck through (weekends for a meeting, dates before the milestone for a receipt).
- States: placeholder, focus, filled, error, disabled; calendar open.

## Date and time (D-158)

When a field needs a time of day too, it is a dropdown, not typed.

- One select box, with the same border, focus and arrow as every dropdown. It reads **17 Nov 2026, 14:30**, or "Choose date and time" when empty.
- It opens one panel in the page's flow, so it pushes the fields below down rather than covering them:
  - the calendar on the left;
  - **Hour** (00–23) and **Min** (00–59) lists on the right, using the calendar's day cells. A chosen hour or minute is filled ink, like the chosen day.
- Footer: **Use now** (a text button) fills the date and the time and closes. **Done** closes. Esc or a click outside also closes.
- Nothing is guessed. Until the date, hour and minute are all picked the value is empty. Closing with only part picked says "Choose the time too." or "Choose the date too."
- Phone: the calendar takes the panel's width, and the hour and minute lists sit side by side under it.
- States: placeholder, open (blue border, ▴), filled, error, disabled.
