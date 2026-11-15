# ListToolbar

The same way to find and narrow records on every list (My work, Registers, Outputs, Setup lists).

- Search box, Filter button (shows how many filters are on), result count on the right in mono.
- Applied filters appear below as removable chips ("Line Invoice preparation ×") with **Clear all**.
- The filter panel opens below the button (380px): the title in a display-caps head, then line, project, state, who it waits on, and a foot with **Clear** and the dark "Show N items" side by side. It applies when the person presses "Show N items", which says how many will show. Focus moves to the first field; Esc or a press outside closes it unapplied.
- On a phone: search plus a 44px filter icon button; the filter panel is a bottom sheet with no grab handle or close button, **Clear** in its head and the dark full-width "Show N items" (control-xl) in its foot; Esc or the scrim close it.
- The result count is a polite live region.
- States: default, typing, filters applied, panel open, no results ("No work matches. Clear filters").
