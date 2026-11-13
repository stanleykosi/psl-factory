# Drawer

Opens from the right over the current page (500px), so people never lose the queue. Used for Start work intake and short forms.

- Head: mono eyebrow (START WORK), display title, one line of context, close button. Body scrolls; footer stays fixed with Cancel and the action.
- The page behind gets the `scrim`; Esc and the close button close it; focus stays inside while open and returns to the opener.
- States: open, needs fixing (validation summary at the top), submitting (busy button), done (closes and shows a toast).
- On phones it becomes a full-height sheet.
