# SplitButton

The Start work control in the top bar of every page. The main part starts the person's most-used line; the arrow opens a menu of every line they may start, plus "Describe it to Tola".

- Lives in the top bar (`control-sm`, 40px). On a phone it becomes "+ Start" in the top bar.
- Shows only lines the signed-in person may start; if they may start none, the control is hidden (not disabled).
- States: default, hover on either half, menu open (arrow half stays pressed), focus on either half.
- The menu is the Menu component; choosing a line opens the Start work drawer.
