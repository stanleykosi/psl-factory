// Month-end no-access view (INV-ACCESS): 403 and 404 look the same and show nothing about the checklist.
import NextLink from 'next/link';

import { buttonClass, PageTitle, Panel, Tag } from '@/components';

export function MonthEndNoAccess() {
  return (
    <Panel>
      <Tag tone="neutral" className="monthend-noaccess__tag">
        NO ACCESS
      </Tag>
      <PageTitle>You can&rsquo;t open this month-end checklist</PageTitle>
      <p className="monthend-plain">It is for people who work on Finance for this month. Nothing about it is shown here.</p>
      <p>
        <NextLink href="/my-work" className={buttonClass('dark', 'lg')}>
          Back to my queue
        </NextLink>
      </p>
    </Panel>
  );
}
