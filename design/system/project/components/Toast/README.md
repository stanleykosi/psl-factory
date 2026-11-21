# Toast

A dark bar at the bottom centre after an action that changed something, with Undo when it can be undone.

- Says what happened and what is next: "R-07 accepted with your edit · next: R-08".
- Stays 6 seconds, or until dismissed; stays while hovered or focused. Never used for errors that need action (use a callout).
- A problem toast (orange top edge) only for a failure that happened in the background, with a link to the fix.
- States: success, success with Undo, problem, dismissible.
- The live region is drawn first and the words written into it a moment later, so screen readers announce them.

## The host (D-151)

One toast host serves the whole app; screens never draw their own toast container.

- Mounted once in the app shell, above the pages, so a toast survives a client-side route change: an action that navigates still shows its toast on the next page.
- Position: bottom centre on desktop. On phones it is full width inside the 16px gutters and sits above any sticky or fixed bar at the bottom of the screen (the assistant composer, a decide or save bar). With a drawer or dialog open, it sits above that panel's own action bar instead, never over its buttons (D-169).
- Newest at the bottom. At most 3 are visible; a fourth drops the oldest.
- It never takes focus. The only focusable parts are Undo, a problem toast's link and the close button, reached by Tab. Hover or focus on a toast holds it past 6 seconds.
- Each toast is its own live region (status, or alert for a problem) and is announced when its words are written in.
- Use it for what a finished action did, in the same words the page used before. Offer Undo only where an undo path exists. Keep a callout for an error that needs action now, the lasting state of a record, and empty or permission states.
