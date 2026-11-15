'use client';

// /setup/rules/finance (SCR-13-desktop-finance-rules, SCR-13-mobile-finance-rules): E-SETUP-RULES with area=finance,
// grouped by the rows' group in first-appearance order. "Set … rules" opens the Set a rule panel for that group's
// editable rows only (PMO-0-3); one panel is open at a time.
import { useState } from 'react';

import { Breadcrumb, Button, Callout, PageTitle, Panel, Tag } from '@/components';

import type { RuleRow } from './contract-proposal';
import { groupButtonLabel, isEditable, valueText } from './format';
import { type Notice, OutcomeNotice, SetRulePanel } from './SetRulePanel';
import { RulesEmpty, RulesReadState, SetupGate, ShowMore, useSetupPhoneBack } from './SetupFrame';
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
            {text === null ? <Tag tone="person">NOT SET</Tag> : <span className="setup-list__value">{text}</span>}
          </li>
        );
      })}
    </ul>
  );
}

export function AreaCrumb({ area }: { area: string }) {
  return (
    <Breadcrumb
      items={[
        { label: 'SETUP', href: '/setup' },
        { label: 'RULES', href: '/setup/rules' },
      ]}
      current={area}
    />
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
  useSetupPhoneBack('RULES');
  const [open, setOpen] = useState<string | null>(null);
  // A save outcome whose group panel closed because the re-read left that group no editable rule (QA-1-1).
  const [closedNotice, setClosedNotice] = useState<Notice | null>(null);
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
        <PageTitle>Finance rules</PageTitle>
        <p className="psl-hint">
          Every value the Finance lines need before they can run. Each is decided by PSL; the factory never guesses. A line stops at
          “Setup needed” only at the step that needs a missing value.
        </p>
        {empty ? (
          <RulesEmpty />
        ) : (
          <>
            <Callout kind="warning">{countText}Real reviewers and approvers come from PSL; none are invented here.</Callout>
            {closedNotice && <OutcomeNotice notice={closedNotice} />}
            <div className="setup-groups">
              {groups.map((group, index) => {
                const editable = group.rows.filter(isEditable);
                const panelId = `setup-group-panel-${index}`;
                const isOpen = open === group.key;
                return (
                  <Panel key={group.key} head={<h2>{group.label}</h2>} className="setup-group">
                    <RuleList rows={group.rows} />
                    {editable.length > 0 && (
                      <div className="setup-groupaction">
                        <Button
                          kind="secondary"
                          size="lg"
                          block
                          aria-expanded={isOpen}
                          aria-controls={panelId}
                          onClick={() => {
                            setClosedNotice(null);
                            setOpen(isOpen ? null : group.key);
                          }}
                        >
                          {groupButtonLabel(group.label)}
                        </Button>
                      </div>
                    )}
                    {editable.length > 0 && (
                      <div id={panelId} hidden={!isOpen}>
                        {isOpen && (
                          <SetRulePanel
                            rows={editable}
                            refresh={refresh}
                            signOut={signOut}
                            staysOpen={(next) => groupRows(next.items).some((g) => g.key === group.key && g.rows.some(isEditable))}
                            onEditorGone={setClosedNotice}
                          />
                        )}
                      </div>
                    )}
                  </Panel>
                );
              })}
            </div>
            <ShowMore state={state} onMore={() => void loadMore()} />
          </>
        )}
      </div>

      <div className="setup-page setup-phone">
        <PageTitle>Finance rules</PageTitle>
        {empty ? (
          <RulesEmpty />
        ) : (
          <>
            {notSet !== undefined && (
              <Callout kind="warning">{notSet} values Not set.</Callout>
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
