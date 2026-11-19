GATE: FAIL
COMMIT: 273d81b5b7cb2d146cd010383cb6f5a40e9e6b96
ATTEMPT: 1

## Summary
- checks.sh failed with exit 1
- Protected paths: none changed
- Commit 273d81b5b7cb, round 2, attempt 1

## checks.sh (last 80 lines of checks.log)

```
                  [36m</label>[39m
                [36m</div>[39m
              [36m</fieldset>[39m
            [36m</div>[39m
            [36m<a[39m
              [33mclass[39m=[32m"psl-callout psl-callout--info sw-tola"[39m
              [33mhref[39m=[32m"/assistant"[39m
            [36m>[39m
              [36m<img[39m
                [33malt[39m=[32m""[39m
                [33mclass[39m=[32m"psl-avatar psl-avatar--tola"[39m
                [33mheight[39m=[32m"32"[39m
                [33msrc[39m=[32m"/agents/tola.png"[39m
                [33mwidth[39m=[32m"32"[39m
              [36m/>[39m
              [36m<span>[39m
                [36m<strong>[39m
                  [0mNot sure which line?[0m
                [36m</strong>[39m
                [0m Describe it to Tola[0m
              [36m</span>[39m
            [36m</a>[39m
            [36m<p[39m
              [33mclass[39m=[32m"psl-hint sw-plain"[39m
            [36m>[39m
              [0mYou only see lines your roles let you start. Ask your Lead if one is missing.[0m
            [36m</p>[39m
          [36m</div>[39m
        [36m</div>[39m
        [36m<div[39m
          [33mclass[39m=[32m"psl-drawer__foot"[39m
        [36m>[39m
          [36m<button[39m
            [33mclass[39m=[32m"psl-btn psl-btn--secondary sw-secondary"[39m
            [33mtype[39m=[32m"button"[39m
          [36m>[39m
            [0mBack[0m
          [36m</button>[39m
          [36m<button[39m
            [33mclass[39m=[32m"psl-btn psl-btn--start sw-primary"[39m
            [33mdisabled[39m=[32m""[39m
            [33mtype[39m=[32m"button"[39m
          [36m>[39m
            [0mNext[0m
          [36m</button>[39m
        [36m</div>[39m
      [36m</aside>[39m
    [36m</div>[39m
  [36m</body>[39m
[36m</html>[39m

- Expected
+ Received

- <button
-   class="psl-btn psl-btn--secondary sw-secondary"
-   type="button"
- >
-   Back
- </button>
+ <input
+   aria-label="Find a line"
+   class="psl-input cmp-search"
+   placeholder="Find a line…"
+   type="search"
+   value=""
+ />

 ❯ tests/start-work.test.tsx:210:56
    208|     await waitFor(() => expect(document.activeElement).toBe(close));
    209|     fireEvent.keyDown(close, { key: 'Tab', shiftKey: true });
    210|     await waitFor(() => expect(document.activeElement).toBe(back));
       |                                                        ^
    211|     fireEvent.keyDown(dialog(), { key: 'Escape' });
    212|     expect(screen.queryByRole('dialog')).toBeNull();
 ❯ runWithExpensiveErrorDiagnosticsDisabled node_modules/@testing-library/dom/dist/config.js:47:12
 ❯ checkCallback node_modules/@testing-library/dom/dist/wait-for.js:124:77
 ❯ Timeout.checkRealTimersCallback node_modules/@testing-library/dom/dist/wait-for.js:118:16

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯[1/1]⎯
```
