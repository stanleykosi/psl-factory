VERDICT: PASS
REVIEWER: reviewer-technical
COMMIT: 5020a86be7320090efa1b2888295f52e205e761a
AUTHORITY: delivery technical review

## Summary
- Round-2 diff 59ce7dc1..5020a86b reviewed. The verified strip, fact tags, phone order, disabled reason and TECH-1-2..4 are all fixed. No blocking findings.

## Findings
- TECH-2-1 | non-blocking | low | frontend | The shared `FactsList` tag change also reaches F-33 W-2706 and F-42 W-3907..3909 ("NOT SET"). Those facts now draw a tag in place of plain words. The builder listed this, and their tests pass unchanged. For design engineer awareness only.
- TECH-2-2 | non-blocking | low | frontend | `caption={forecast}` applies to every section of the `cash_forecast` line, including the older W-2004 D-62 example. This is harmless today, because `captionText` only matches a one-item, untitled, plain text section. Be aware of it if more forecast fixtures are added.
- TECH-1-1 | carried | non-blocking | frontend | The stale-409 gap in the shared InlineDecide is unchanged. It lands with F-35/F-39. TECH-1-5 (the "received" wording) is still a product question.

## Verified
- Strip: `FiguresStrip` draws `money`, `value` or `<Unknown />` as returned. There is no arithmetic and Unknown never becomes 0. The VERIFIED cell's tone comes from the fixture tag (`data-tone`), and the tag's words are not drawn twice. The fixture change only adds the `tag` to V-6.
- Fact tags: `FactsList` draws `item.tag` from data, with the tone mapped by `tagTone`. Words that equal the tag's label are not shown twice.
- Phone order: `ReconcilePanel` is rendered after the side column, inside the workspace. The overview draws none for `cash_forecast`, so there is no double render. The test checks the order and that there is exactly one `.resp-reconcile`.
- Disabled reason: `askFirst` and `proofFirst` are gated on `internal`. The hint is tied to the button by `aria-describedby`. Other lines are unchanged. `response.test.tsx` is unchanged and passes.
- Scope: the `Sections.tsx` changes are opt-in (`strip` and `caption` props, true only for `forecastLine`). The CSS is the compound `.ws-section--figures.ws-section--strip` plus new classes. The tag change is the one global effect (TECH-2-1).
- TECH-1-2: a nested `section` is used, with no `aside aside`. TECH-1-3: the line key is written once, as `INTERNAL_RECONCILE_LINE`. TECH-1-4: the phone count check is added.
- Regression: with `src` reverted to 59ce7dc1, 6 of the 42 cash-forecast tests fail. At the head, cash-forecast plus response tests give 95 passed. The worktree was restored to the head with no changes left.
- Gate PASS (checks 2882).
