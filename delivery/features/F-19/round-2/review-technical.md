VERDICT: PASS
COMMIT: 41b4925c441959c3a4fc2b7eaf8437fa35791109
REVIEWER: reviewer-technical
AUTHORITY: delegated technical review

## Findings
- TECH-2-1 | non-blocking | low | coordinator | Spec line 48 and AC 10 still say Save is disabled until both inputs are filled. D-75(a) replaces that rule, so the spec text should be updated to match. The carried-over TECH-1-1 fixture-row correction (Tamarind) is also still open in the spec.

## Review notes (lean re-review of effdc3f5..41b4925c)
- Save per D-75(a): `submit` returns early only while a request is in flight. A blank or whitespace-only name or email builds field messages and calls `setNotice` with kind `invalid`, which is the same path the 422 handler uses. It does this before `pressed.current` is set and before any request, so an empty press sends nothing. The button is disabled only while busy. The double-press guard and the single-PUT body are unchanged.
- `clients__needed` is applied only while `!contact.set`.
- The `clients__bar` wrapper does not change the form semantics. On desktop it is `display: contents`.
- `destinationForPath`: `/clients` and `/clients/...` map to Projects. `/clientsx` and `/client` do not match, and the new test covers both. The other routes are untouched.
- AC-10 test changes are justified and nothing is weakened. The only assertions removed are `disabled === true` in the empty and blank-email states, and D-75(a) reverses those. The replacements are stricter: they check that `puts()` has length 0 for an empty press and for a name-only press, that the per-field messages are correct, and where focus lands. The single-PUT, double-press and reload assertions are intact.
- The CSS changes are presentational only. On phone the form panel loses its chrome but keeps its h2, visually hidden, so the accessible name survives.
