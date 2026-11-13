# IconButton

A square button with an icon and no visible label, for close, filter on a phone, more actions and clear.

- Always give it an `aria-label` naming the action ("Close", "Filter", "More actions").
- 44 × 44px so it is a full touch target. The bare variant (no outline) is for close and clear inside a drawer header, toast or field.
- States: default, hover (`steel`), pressed (`neutral-tint`), focus ring, disabled.
- A count on a filter button uses the count badge, never a dot.
