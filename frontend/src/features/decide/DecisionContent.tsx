// SCR-03 decision content: the header and the version rows. Only values from the live task and work reads are
// shown; a board part with no live source is left out (D-182).
import Link from 'next/link';
import { useEffect, useRef, type ReactNode } from 'react';

import type { LiveTaskRead, LiveWork } from '@/api/types';
import { Breadcrumb, formatDayTime, Unknown } from '@/components';
import { showSampleLabel } from '@/shell/sample';
import { SampleLabel } from '@/shell/SampleLabel';

import { formatAmount, shortHash, type Packet } from './format';

// The boards write these as "12 Nov 10:30" (no year, no WAT); the shared formatter's "12 Nov 2026 10:30 WAT" stays for the screens whose boards do not draw one.
export function When({ at }: { at: string }) {
  return <time dateTime={at}>{formatDayTime(at)}</time>;
}

type HeaderProps = {
  work: LiveWork | null;
  title: string;
  /** The board's visible trail ("DECISIONS / 2 OF 5"); the Breadcrumb nav stays for screen readers. */
  trail?: ReactNode;
  /** The done view's banner line ("YOU APPROVED · 10:47"). */
  eyebrow?: ReactNode;
  sub?: string;
  banner?: 'success' | 'neutral';
  /** The stale phone board draws no title: the header stays for screen readers only below 720px. */
  quietOnPhone?: boolean;
  /** Move focus to the title on arrival (the done view, after a decision). */
  focusHeading?: boolean;
};

/** The common header: the trail, the title (in a banner on the done view) and the sub-line. */
export function DecideHeader({ work, title, trail, eyebrow, sub, banner, quietOnPhone, focusHeading }: HeaderProps) {
  const ref = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    if (focusHeading) ref.current?.focus();
  }, [focusHeading]);
  const heading = (
    <h1 ref={ref} tabIndex={focusHeading ? -1 : undefined} className="shell-title">
      {title}
    </h1>
  );
  const sample = work?.sample && showSampleLabel();
  return (
    <header className={`decide-header${quietOnPhone ? ' decide-header--quiet' : ''}`}>
      <div className="cmp-sr">
        <Breadcrumb items={[{ label: 'My work', href: '/my-work' }]} current={work?.title ?? 'Decision'} />
      </div>
      {trail && <p className="decide-trail">{trail}</p>}
      {banner ? (
        <div className={`decide-banner decide-banner--${banner}`}>
          {eyebrow && <p className="decide-eyebrow">{eyebrow}</p>}
          {heading}
        </div>
      ) : (
        <div className="decide-titleline">
          {heading}
          {(sub || sample) && (
            <p className="decide-sub">
              {sub && <span>{sub}</span>}
              {/* The shared frame label only (design engineer, 14 Nov 2026: no screen-level sample tags). */}
              {work?.sample && <SampleLabel />}
            </p>
          )}
        </div>
      )}
    </header>
  );
}

/** The actionable trail: "Decisions / 2 of 5" (the place only when the live list holds this work). */
export function DecisionTrail({ queue }: { queue?: string }) {
  return (
    <>
      <Link href="/my-work">Decisions</Link>
      {queue && ` / ${queue}`}
    </>
  );
}

/** An amount as the boards' value cells; a missing packet or amount reads Unknown (INV-UNKNOWN: never 0). */
export function AmountValue({ packet }: { packet: Pick<Packet, 'amount' | 'currency'> | null | undefined }) {
  const text = formatAmount(packet);
  if (text === null) return <Unknown />;
  return <span className="psl-amount">{text}</span>;
}

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="decide-row">
      <dt>{label}</dt>
      <dd>{children}</dd>
    </div>
  );
}

/** The recipient the task names now, and the earlier one when it changed. */
export function recipientOf(read: LiveTaskRead): { current: string | null; earlier: string | null } {
  const current = read.recipient_change?.current ?? read.invoice_packet?.recipient ?? null;
  const earlier = read.recipient_change?.earlier ?? null;
  return { current, earlier: earlier !== null && earlier !== current ? earlier : null };
}

/** The decision rows: amount, recipient (with a changed line), version and the packet's sources. */
export function DecisionRows({ read }: { read: LiveTaskRead }) {
  const packet = read.invoice_packet;
  const { current, earlier } = recipientOf(read);
  return (
    <dl className="decide-rows" aria-label="Decision">
      <Row label="Amount">
        <AmountValue packet={packet} />
      </Row>
      {current && (
        <Row label="To">
          {current}
          {earlier && <span className="decide-changed decide-recipient-changed"> Recipient changed. It was {earlier}.</span>}
        </Row>
      )}
      {packet && (
        <Row label="Version">
          {`Version ${packet.version}`} <span className="decide-muted decide-tech">· checksum {shortHash(packet.sha256)}</span>
        </Row>
      )}
      {packet && packet.sources.length > 0 && (
        <Row label="Sources">
          <ul className="decide-list">
            {packet.sources.map((source) => (
              <li key={source.id}>
                {source.kind} version {source.version} <span className="decide-muted decide-tech">· {shortHash(source.sha256)}</span>
              </li>
            ))}
          </ul>
        </Row>
      )}
    </dl>
  );
}
