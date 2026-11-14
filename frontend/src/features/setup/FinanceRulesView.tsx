'use client';

// /setup/rules/finance (SCR-13-desktop-finance-rules, SCR-13-mobile-finance-rules): E-SETUP-RULES with area=finance,
// grouped by the rows' group in first-appearance order. "Set … rules" opens the Set a rule panel for that group's
// editable rows only (PMO-0-3); one panel is open at a time.
import Link from 'next/link';
import { useState } from 'react';

import { WarningIcon } from '@/shell/icons';

import type { RuleRow } from './contract-proposal';
import { groupButtonLabel, isEditable, valueText } from './format';
import { SetRulePanel } from './SetRulePanel';
import { PhoneBack, RulesEmpty, RulesReadState, SetupGate, ShowMore } from './SetupFrame';
import { useSetupRules } from './useSetupRules';

const OTHER = 'Other Finance rules';
type Group = { key: string; label: string; rows: RuleRow[] };

function groupRows(items: RuleRow[]): Group[] {
  const groups = new Map<string, Group>();
  const other: Group = { key: '', label: OTHER, rows: [] };
  for (const row of items) {
    if (!row.group) {
      other.rows.push(row);
      continue;
    }
    if (!groups.has(row.group)) groups.set(row.group, { key: row.group, label: row.group_label ?? row.group, rows: [] });
    groups.get(row.group)!.rows.push(row);
  }
  return other.rows.length > 0 ? [...groups.values(), other] : [...groups.values()];
}

export function RuleList({ rows }: { rows: RuleRow[] }) {
  return (
    <ul className="setup-list">
      {rows.map((row) => {
        const text = valueText(row);
        return (
          <li key={row.component}>
            <span>{row.name}</span>
            {text === null ? <span className="psl-tag psl-tag--person setup-tag">NOT SET</span> : <span className="setup-list__value">{text}</span>}
          </li>
        );
      })}
    </ul>
  );
}

export function AreaCrumb({ area }: { area: string }) {
  return (
    <nav aria-label="Breadcrumb">
      <p className="psl-crumb setup-crumb">
        <Link href="/setup/rules">SETUP</Link> / <Link href="/setup/rules">RULES</Link> / <span aria-current="page">{area}</span>
      </p>
    </nav>
  );
}

export function FinancePageView() {
  return (
    <SetupGate>
      <FinanceRulesView />
    </SetupGate>
  );
}

function FinanceRulesView() {
  const { state, retry, refresh, loadMore, signOut } = useSetupRules('finance');
  const [open, setOpen] = useState<string | null>(null);
  if (state.status !== 'ready') return <RulesReadState state={state} retry={() => void retry()} />;

  const { page, items } = state;
  const groups = groupRows(items);
  const notSet = page.not_set_count;
  const allUnset = !state.nextCursor && items.length > 0 && items.every((row) => !row.set);
  const countText = notSet === undefined ? '' : allUnset ? `All ${notSet} values are Not set. ` : `${notSet} values are Not set. `;
  const empty = items.length === 0;
  const phoneGroups = groups.slice(0, 3);
  const moreGroups = groups.length - phoneGroups.length;

  return (
    <>
      <div className="setup-page setup-desktop">
        <AreaCrumb area="FINANCE" />
        <h1 className="setup-title setup-title--area">Finance rules</h1>
        <p className="setup-lead">
          Every value the Finance lines need before they can run. Each is decided by PSL; the factory never guesses. A line stops at
          “Setup needed” only at the step that needs a missing value.
        </p>
        {empty ? (
          <RulesEmpty />
        ) : (
          <>
            <div className="psl-callout psl-callout--warning">
              <WarningIcon />
              <span>{countText}Real reviewers and approvers come from PSL; none are invented here.</span>
            </div>
            <div className="setup-groups">
              {groups.map((group, index) => {
                const editable = group.rows.filter(isEditable);
                const panelId = `setup-group-panel-${index}`;
                const isOpen = open === group.key;
                return (
                  <section key={group.key} className="psl-panel setup-group" aria-labelledby={`setup-group-${index}`}>
                    <h2 className="psl-panel__head" id={`setup-group-${index}`}>
                      {group.label}
                    </h2>
                    <div className="psl-panel__body">
                      <RuleList rows={group.rows} />
                      {editable.length > 0 && (
                        <div className="setup-groupaction">
                          <button
                            type="button"
                            className="psl-btn psl-btn--secondary psl-btn--lg psl-btn--block"
                            aria-expanded={isOpen}
                            aria-controls={panelId}
                            onClick={() => setOpen(isOpen ? null : group.key)}
                          >
                            {groupButtonLabel(group.label)}
                          </button>
                        </div>
                      )}
                      {editable.length > 0 && (
                        <div id={panelId} hidden={!isOpen}>
                          {isOpen && <SetRulePanel rows={editable} refresh={refresh} signOut={signOut} />}
                        </div>
                      )}
                    </div>
                  </section>
                );
              })}
            </div>
            <ShowMore state={state} onMore={() => void loadMore()} />
          </>
        )}
      </div>

      <div className="setup-page setup-phone">
        <PhoneBack label="RULES" />
        <h1 className="setup-phone-title setup-phone-title--area">Finance rules</h1>
        {empty ? (
          <RulesEmpty />
        ) : (
          <>
            {notSet !== undefined && (
              <div className="psl-callout psl-callout--warning">
                <WarningIcon />
                <span>{notSet} values Not set.</span>
              </div>
            )}
            {phoneGroups.map((group) => (
              <div key={group.key} className="setup-card">
                <strong>{group.label}</strong>
                <RuleList rows={group.rows} />
              </div>
            ))}
            {moreGroups > 0 && (
              <p className="setup-more">
                + {moreGroups} MORE {moreGroups === 1 ? 'LINE' : 'LINES'} · OPEN ON DESKTOP
              </p>
            )}
          </>
        )}
      </div>
    </>
  );
}
