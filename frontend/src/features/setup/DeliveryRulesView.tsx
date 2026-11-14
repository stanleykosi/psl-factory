'use client';

// /setup/rules/delivery (SCR-13-desktop-delivery-rules, SCR-13-mobile-delivery-rules): E-SETUP-RULES with
// area=delivery, read-only as drawn.
import { InfoIcon } from './icons';
import { AreaCrumb, RuleList } from './FinanceRulesView';
import { valueText } from './format';
import { PhoneBack, RulesEmpty, RulesReadState, SetupGate, ShowMore } from './SetupFrame';
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
  if (state.status !== 'ready') return <RulesReadState state={state} retry={() => void retry()} />;

  const { items } = state;
  const empty = items.length === 0;
  const head = items[0]?.area_label ?? 'Delivery';

  return (
    <>
      <div className="setup-page setup-desktop">
        <AreaCrumb area="DELIVERY" />
        <h1 className="setup-title setup-title--area">Delivery rules</h1>
        {empty ? (
          <RulesEmpty />
        ) : (
          <div className="setup-columns">
            <div className="setup-main">
              <section className="psl-panel" aria-labelledby="setup-delivery-head">
                <h2 className="psl-panel__head" id="setup-delivery-head">
                  {head}
                </h2>
                <div className="psl-panel__body">
                  <div className="psl-tablewrap">
                    <table className="psl-table setup-table setup-table--delivery">
                      <thead>
                        <tr>
                          <th scope="col">RULE</th>
                          <th scope="col">VALUE</th>
                          <th scope="col">USED BY</th>
                        </tr>
                      </thead>
                      <tbody>
                        {items.map((row) => {
                          const text = valueText(row);
                          return (
                            <tr key={row.component}>
                              <td>{row.name}</td>
                              <td>{text === null ? <span className="psl-tag psl-tag--person setup-tag">NOT SET</span> : text}</td>
                              <td>{row.used_by?.join(', ')}</td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                  <ShowMore state={state} onMore={() => void loadMore()} />
                </div>
              </section>
              <div className="psl-callout psl-callout--info">
                <InfoIcon />
                <span>These are PSL’s decisions. Until a rule is set, the line that needs it stops as “Setup needed” instead of guessing.</span>
              </div>
            </div>
            <aside className="setup-aside setup-aside--next" aria-labelledby="setup-next-head">
              <section className="psl-panel">
                <h2 className="psl-panel__head" id="setup-next-head">
                  Next
                </h2>
                <div className="psl-panel__body">
                  <p className="setup-plain">Each rule is versioned. Changing one doesn’t change work already finished.</p>
                </div>
              </section>
            </aside>
          </div>
        )}
      </div>

      <div className="setup-page setup-phone">
        <PhoneBack label="RULES" />
        <h1 className="setup-phone-title setup-phone-title--area">Delivery rules</h1>
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
