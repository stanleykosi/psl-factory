GATE: FAIL
COMMIT: 473090df18b54f3897f876ef417cac262980974e
ATTEMPT: 1

## Summary
- checks.sh failed with exit 1
- Protected paths: none changed
- Commit 473090df18b5, round 1, attempt 1

## checks.sh (last 80 lines of checks.log)

```
            </svg>
            <span>
              Sign-in isn’t working right now. Try again in a moment. Nothing was changed.
+           </span>
+         </div>
+         <div
+           class="psl-field"
+         >
+           <label
+             class="psl-label"
+             for="_r_26_-control"
+             id="_r_26_-control-label"
+           >
+             Work email or sign-in name
+           </label>
+           <input
+             autocapitalize="none"
+             autocomplete="username"
+             class="psl-input"
+             id="_r_26_-control"
+             name="username"
+             spellcheck="false"
+             type="text"
+             value="someone@psl.example"
+           />
+         </div>
+         <div
+           class="psl-field"
+         >
+           <label
+             class="psl-label"
+             for="_r_27_-control"
+             id="_r_27_-control-label"
+           >
+             Password
+           </label>
+           <input
+             autocomplete="current-password"
+             class="psl-input"
+             id="_r_27_-control"
+             name="password"
+             type="password"
+             value=""
+           />
+         </div>
+         <label
+           class="psl-check cmp-check"
+         >
+           <input
+             type="checkbox"
+           />
+           <span>
+             Keep me signed in
            </span>
+         </label>
+         <button
+           class="psl-btn psl-btn--lg psl-btn--block"
+           type="submit"
+         >
+           Sign in
+         </button>
+         <p
+           class="signin-forgot"
+         >
+           Forgot your password? Reset opens in a later release. Ask your administrator for help.
+         </p>
+       </form>
+     </main>
    </div>
+ </body>

 ❯ tests/sign-in.test.tsx:226:36
    224|     const alert = await screen.findByRole('alert');
    225|     expect(alert.textContent).toBe(wording);
    226|     expect(document.activeElement).toBe(alert);
       |                                    ^
    227|     expect(passField().value).toBe('');
    228|     expect(userField().value).toBe('someone@psl.example');

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯[1/1]⎯
```
