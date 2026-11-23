'use client';

// SCR-43 Delivery tab: live has no delivery source, so the route says so and shows nothing else.
import { Panel } from '@/components';

export function DeliveryTab() {
  return (
    <Panel head="Delivery is not available yet" headingLevel={2}>
      <p className="projects__plain">This project’s delivery view is not connected yet.</p>
    </Panel>
  );
}
