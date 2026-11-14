'use client';

// /setup/rules (SCR-13-desktop-rules, SCR-13-mobile-rules). Every value comes from E-SETUP-RULES: Not set only when
// set is false, counts only from the count fields, editing only where the row allows it. Both layouts render and
// CSS shows one; the phone is read-only as drawn (D-15).
import Link from 'next/link';
import { useState } from 'react';

import { WarningIcon } from '@/shell/icons';

import type { RuleRow } from './contract-proposal';
import { areaHref, isEditable, linkHref, valueText, versionText } from './format';
import { type Notice, OutcomeNotice, SetRulePanel } from './SetRulePanel';
import { RulesEmpty, RulesReadState, SetupFrame, SetupGate, ShowMore, useSetupPhoneBack } from './SetupFrame';
import { useSetupRules } from './useSetupRules';

export function RulesPageView() {
  return (
    <SetupGate>
      <RulesView />
    </SetupGate>
  );
}

export function notSetBanner(n: number) {
  return n === 1
    ? '1 rule isn’t set yet. Work that needs it waits as “Setup needed”; nothing guesses a rule. These are PSL’s decisions (see the approvals worksheet).'
    : `${n} rules aren’t set yet. Work that needs them waits as “Setup needed”; nothing guesses a rule. These are PSL’s decisions (see the approvals worksheet).`;
}

function AreaText({ row }: { row: RuleRow }) {
  const href = areaHref(row);
  if (!row.area_label) return null;
  return href ? <Link href={href}>{row.area_label}</Link> : <>{row.area_label}</>;
}

function ValueCell({ row }: { row: RuleRow }) {
  const text = valueText(row);
  if (text === null) return <span className="setup-notset">Not set</span>;
  const href = linkHref(row);
  return href ? <Link href={href}>{text}</Link> : <>{text}</>;
}

function VersionCell({ row }: { row: RuleRow }) {
  if (row.holds_work) return <span className="psl-tag psl-tag--person setup-tag">HOLDS WORK</span>;
  const text = versionText(row);
  return text ? <span className="setup-version">{text}</span> : null;
}

function RulesView() {
  const { state, retry, refresh, loadMore, signOut } = useSetupRules();
  useSetupPhoneBack();
  // A save outcome whose panel closed because the re-read left no editable rule (QA-1-1); shown only while the panel
  // stays closed, so a later Show more that brings the panel back never keeps a stale "has closed" (TECH-2-1).
  const [closedNotice, setClosedNotice] = useState<Notice | null>(null);
  if (state.status !== 'ready') return <RulesReadState state={state} retry={() => void retry()} />;

  const { page, items } = state;
  const editable = items.filter(isEditable);
  const notSet = page.not_set_count;
  const empty = items.length === 0;

  return (
    <>
      <div className="setup-page setup-desktop">
        <SetupFrame current="rules" rolesMissing={page.roles_missing_count} notSet={notSet} />
        {empty ? (
          <RulesEmpty />
        ) : (
          <>
            {notSet !== undefined && notSet > 0 && (
              <div className="psl-callout psl-callout--warning">
                <WarningIcon />
                <span>{notSetBanner(notSet)}</span>
              </div>
            )}
            {closedNotice && editable.length === 0 && <OutcomeNotice notice={closedNotice} />}
            <div className="setup-columns">
              <section className="setup-main" aria-label="Rules">
                <div className="psl-tablewrap">
                  <table className="psl-table setup-table">
                    <thead>
                      <tr>
                        <th scope="col">RULE</th>
                        <th scope="col">AREA</th>
                        <th scope="col">CURRENT VALUE</th>
                        <th scope="col">VERSION</th>
                      </tr>
                    </thead>
                    <tbody>
                      {items.map((row) => (
                        <tr key={row.component}>
                          <td>
                            <strong>{row.name}</strong>
                          </td>
                          <td>
                            <AreaText row={row} />
                          </td>
                          <td>
                            <ValueCell row={row} />
                          </td>
                          <td>
                            <VersionCell row={row} />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <ShowMore state={state} onMore={() => void loadMore()} />
              </section>
              {editable.length > 0 && (
                <aside className="setup-aside" aria-label="Set a rule">
                  <SetRulePanel
                    rows={editable}
                    refresh={refresh}
                    signOut={signOut}
                    staysOpen={(next) => next.items.some(isEditable)}
                    onEditorGone={setClosedNotice}
                  />
                </aside>
              )}
            </div>
          </>
        )}
      </div>

      <div className="setup-page setup-phone">
        <h1 className="setup-phone-title">{notSet === undefined ? 'Rules' : `Rules · ${notSet} not set`}</h1>
        {empty ? (
          <RulesEmpty />
        ) : (
          <ul className="setup-cards">
            {items.map((row) => {
              const text = valueText(row);
              return (
                <li key={row.component} className="setup-card">
                  <strong>{row.name}</strong>
                  <span className={`setup-card__line${text === null ? ' is-notset' : ''}`}>
                    {text ?? 'Not set'}
                    {row.area_label && (
                      <>
                        {' · '}
                        <AreaText row={row} />
                      </>
                    )}
                  </span>
                </li>
              );
            })}
          </ul>
        )}
        <ShowMore state={state} onMore={() => void loadMore()} />
      </div>
    </>
  );
}
