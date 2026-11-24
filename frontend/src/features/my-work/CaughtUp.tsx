'use client';

import Image from 'next/image';

import { Button } from '@/components';
import { StartWorkButton } from '@/features/start-work/StartWorkButton';
import { useMe } from '@/shell/AppShell';

/**
 * SCR-01-*-empty: Needs me is empty. Says so, points to the work the person started and offers Start work. The count of
 * started things is the `mine` queue's own total; when the server could not give one the line never says 0.
 */
export function CaughtUp({ started, onSeeStarted }: { started: number | undefined; onSeeStarted: () => void }) {
  const me = useMe();
  return (
    <div className="my-work__caughtwrap">
      <div className="my-work__caughtup">
        <section aria-label="You’re all caught up" className="my-work__nothing">
          <Image src="/agents/tola-done.png" alt="Tola, the PMO agent, giving a thumbs up" width={120} height={170} className="my-work__mascot" />
          <div className="my-work__nothingtext">
            <h2>You&rsquo;re all caught up</h2>
            <p>
              {started === undefined
                ? 'Things you started keep moving. We’ll alert you on WhatsApp when one needs you.'
                : started === 0
                  ? 'Nothing you started is still open. We’ll alert you on WhatsApp when something needs you.'
                  : `${started} ${started === 1 ? 'thing' : 'things'} you started ${started === 1 ? 'is' : 'are'} moving. We’ll alert you on WhatsApp when one needs you.`}
            </p>
            <div className="my-work__nothingactions">
              {me.startable_lines.length > 0 && <StartWorkButton variant="bar" />}
              <Button kind="secondary" onClick={onSeeStarted}>
                See what you started
              </Button>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
