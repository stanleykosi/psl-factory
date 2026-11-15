GATE: FAIL
COMMIT: 28c13dbcca5af9b6db6f276e2878c43a487a8958
ATTEMPT: 1

## Summary
- checks.sh failed with exit 1
- Protected paths: none changed
- Commit 28c13dbcca5a, round 2, attempt 1

## checks.sh (last 80 lines of checks.log)

```
+               >
+                 Delivery
+               </a>
+             </span>
+           </li>
+           <li
+             class="setup-card"
+           >
+             <strong>
+               Invoice payment terms default
+             </strong>
+             <span
+               class="setup-card__line"
+             >
+               From each signed SOW
+                · 
+               <a
+                 href="/setup/rules/finance"
+               >
+                 Finance
+               </a>
+             </span>
+           </li>
+           <li
+             class="setup-card"
+           >
+             <strong>
+               Who may record an RFP outcome
+             </strong>
+             <span
+               class="setup-card__line is-notset"
+             >
+               Not set
+                · 
+               Pre-sale
+             </span>
+           </li>
+           <li
+             class="setup-card"
+           >
+             <strong>
+               Who may adjust a project's costing
+             </strong>
+             <span
+               class="setup-card__line is-notset"
+             >
+               Not set
+                · 
+               Pre-sale
+             </span>
+           </li>
+           <li
+             class="setup-card"
+           >
+             <strong>
+               Costing adjustment limit (per role)
+             </strong>
+             <span
+               class="setup-card__line is-notset"
+             >
+               Not set
+                · 
+               Pre-sale
+             </span>
+           </li>
+         </ul>
+       </div>
+     </main>
+   </div>
+ </body>

 ❯ tests/setup-rules.test.tsx:422:36
    420|     await waitFor(() => expect(desktop().getByRole('alert').textConten…
    421|     expect(screen.queryByRole('region', { name: 'Set a rule' })).toBeN…
    422|     expect(document.activeElement).toBe(desktop().getByRole('alert'));
       |                                    ^
    423|     expect(saves()).toHaveLength(1);
    424|     expect(reads()).toHaveLength(2);

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯[1/1]⎯
```
