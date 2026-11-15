'use client';

// /setup/rules/delivery (SCR-13-desktop-delivery-rules, SCR-13-mobile-delivery-rules): E-SETUP-RULES with
// area=delivery, read-only as drawn.
import { Callout, PageTitle, Panel, Table, Tag } from '@/components';

import { AreaCrumb, RuleList } from './FinanceRulesView';
import { valueText } from './format';
import { RulesEmpty, RulesReadState, SetupGate, ShowMore, useSetupPhoneBack } from './SetupFrame';
import { useSetupRules } from './useSetupRules';

export function DeliveryPageView() {
  return (
    <SetupGate>
      <DeliveryRulesView />
    </SetupGate>
  );
}

function DeliveryRulesView() {
  const { state, retry, loadMore } = useSetupRules('delivery');
  useSetupPhoneBack('RULES');
  if (state.status !== 'ready') return <RulesReadState state={state} retry={() => void retry()} />;

  const { items } = state;
  const empty = items.length === 0;
  const head = items[0]?.area_label ?? 'Delivery';

  return (
    <>
      <div className="setup-page setup-desktop">
        <AreaCrumb area="DELIVERY" />
        <PageTitle size={32}>Delivery rules</PageTitle>
        {empty ? (
          <RulesEmpty />
        ) : (
          <div className="setup-columns">
            <div className="setup-main">
              <Panel head={<h2>{head}</h2>}>
                <Table
                  caption="Delivery rules and where they are used"
                  columns={[
                    { key: 'rule', header: 'RULE', cell: (row) => row.name },
                    { key: 'value', header: 'VALUE', cell: (row) => valueText(row) ?? <Tag tone="person">NOT SET</Tag> },
                    { key: 'used', header: 'USED BY', cell: (row) => row.used_by?.join(', ') },
                  ]}
                  rows={items}
                  rowKey={(row) => row.component}
                  empty="No rules to show."
                />
                <ShowMore state={state} onMore={() => void loadMore()} />
              </Panel>
              <Callout kind="info">These are PSL’s decisions. Until a rule is set, the line that needs it stops as “Setup needed” instead of guessing.</Callout>
            </div>
            <aside className="setup-aside setup-aside--next" aria-label="Next">
              <Panel head={<h2>Next</h2>}>
                <p className="setup-plain">Each rule is versioned. Changing one doesn’t change work already finished.</p>
              </Panel>
            </aside>
          </div>
        )}
      </div>

      <div className="setup-page setup-phone">
        <PageTitle phoneSize={20}>Delivery rules</PageTitle>
        {empty ? (
          <RulesEmpty />
        ) : (
          <div className="setup-card">
            <RuleList rows={items} />
          </div>
        )}
        <ShowMore state={state} onMore={() => void loadMore()} />
      </div>
    </>
  );
}
