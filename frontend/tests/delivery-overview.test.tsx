// @vitest-environment jsdom
// F-32 SCR-43: the Delivery tab draws E-PROJECT `delivery[]` as returned (contract mock only). Rows, tones, links, the
// sub-nav, Tola's check and the fallbacks, unknowns, access, and that nothing is counted, ruled or written here.
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { setImmediate as realImmediate } from 'node:timers';

import { act, render, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ProjectJourneyPage } from '@/features/projects/ProjectJourney';
import { AppShell } from '@/shell/AppShell';

import { bellFeed, isBellFeed } from './bell-feed';

vi.mock('next/navigation', () => ({
  usePathname: () => '/projects/P-0101/delivery',
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), prefetch: vi.fn() }),
}));

// eslint-disable-next-line @typescript-eslint/no-explicit-any
type Body = Record<string, any>;
const fixture = (): Body => JSON.parse(readFileSync(join(__dirname, '../mock/fixtures/projects/P-0101.json'), 'utf8'));
const me = (persona: string) => JSON.parse(readFileSync(join(__dirname, `../mock/fixtures/me.${persona}.json`), 'utf8'));
const json = (status: number, body: unknown) => new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });

let calls: Request[];
let respond: () => Response;
let persona = 'pm';

beforeEach(() => {
  persona = 'pm';
  calls = [];
  respond = () => json(200, fixture());
  vi.stubGlobal(
    'fetch',
    vi.fn(async (request: Request) => {
      if (isBellFeed(request)) return bellFeed();
      if (new URL(request.url).pathname === '/api/v1/me') return json(200, me(persona));
      calls.push(request);
      return respond();
    }),
  );
});
afterEach(() => vi.unstubAllGlobals());

async function until(check: () => void, tries = 100) {
  for (let i = 0; ; i++) {
    try {
      check();
      return;
    } catch (error) {
      if (i >= tries) throw error;
    }
    await act(async () => {
      await new Promise((r) => realImmediate(r));
    });
  }
}

async function open(caseId = 'P-0101') {
  render(
    <AppShell>
      <ProjectJourneyPage caseId={caseId} tab="delivery" />
    </AppShell>,
  );
  await until(() => expect(screen.queryByText('Loading…')).toBeNull());
  await until(() => expect(document.querySelector('main')!.textContent).not.toBe(''));
}

const rows = () => [...document.querySelectorAll('ol.delivery__rows > li')] as HTMLElement[];
const tags = (row: HTMLElement) => row.querySelector('.psl-tag') as HTMLElement;
const main = () => document.querySelector('main')!.textContent!;

describe('tabs', () => {
  it('the project tab bar shows Delivery after Journey, selected, linked to the delivery path', async () => {
    await open();
    const tabs = within(screen.getByRole('tablist', { name: 'Project' })).getAllByRole('tab');
    expect(tabs.map((t) => t.textContent)).toEqual(['Journey', 'Delivery', 'Milestones 4', 'Documents 6', 'Money', 'Registers 6', 'Actions 9']);
    expect(tabs[1].getAttribute('href')).toBe('/projects/P-0101/delivery');
    expect(tabs.map((t) => t.getAttribute('aria-selected'))).toEqual(['false', 'true', 'false', 'false', 'false', 'false', 'false']);
    expect(screen.getByRole('tabpanel', { name: 'Delivery' })).toBeTruthy();
  });
});

describe('rows', () => {
  it('shows six rows numbered 01 to 06 in the returned order, with reference or a dash, tag and date or reason', async () => {
    await open();
    expect(calls).toHaveLength(1);
    expect(rows().map((r) => r.textContent)).toEqual([
      '01Release gatesREL-0091Release ready · 25 Mar',
      '02Go-live acceptanceGLV-0104Accepted · Signed 02 Apr',
      '03HypercareHYP-0062Running · Day 10 of the window',
      '04ArchiveARC-0130Archived and verified · 05 Apr',
      '05Handover to SupportHND-0048Support listed 2 gaps · 10 Apr',
      '06Closure—Not yet · Needs hypercare, handover, retrospective',
    ]);
    expect(rows().map((r) => r.querySelector('a')?.getAttribute('href') ?? null)).toEqual(['/work/W-2503', '/work/W-2510', null, null, null, null]);
    expect(main()).toContain('The delivery lines, in order');
  });

  it('reordering the data reorders the page', async () => {
    const body = fixture();
    body.delivery.reverse();
    respond = () => json(200, body);
    await open();
    expect(rows().map((r) => r.textContent!.slice(0, 2))).toEqual(['01', '02', '03', '04', '05', '06']);
    expect(rows()[0].textContent).toContain('Closure');
    expect(rows()[5].textContent).toContain('Release gates');
  });

  it('a verified state with an uncertain gate tone shows the uncertain tone: tone comes only from the returned tone', async () => {
    const body = fixture();
    body.delivery[0].state = 'verified';
    body.delivery[0].gate = { label: 'Release ready', tone: 'uncertain' };
    respond = () => json(200, body);
    await open();
    expect(tags(rows()[0]).className).toContain('psl-tag--waiting');
    expect(tags(rows()[0]).className).not.toContain('psl-tag--done');
  });

  it('five rows show five rows with the same heading; nothing is counted', async () => {
    const body = fixture();
    body.delivery.pop();
    respond = () => json(200, body);
    await open();
    expect(rows()).toHaveLength(5);
    expect(main()).toContain('The delivery lines, in order');
    expect(document.querySelector('.delivery__panel')!.textContent).not.toMatch(/\b\d+ of \d+\b|\bdone\b/i);
  });

  it('a work_id that is not a plain record id is not a link', async () => {
    const body = fixture();
    body.delivery[0].work_id = '../x';
    respond = () => json(200, body);
    await open();
    expect(rows()[0].querySelector('a')).toBeNull();
    expect(rows()[0].textContent).toContain('Release gates');
  });
});

describe('nothing ruled in the browser', () => {
  it('draws the line-order sentence only when delivery_summary.note is returned', async () => {
    await open();
    expect(main()).toContain('Closure needs all of them');
  });

  it('a copy without the note shows no sentence', async () => {
    const body = fixture();
    delete body.delivery_summary;
    respond = () => json(200, body);
    await open();
    expect(main()).not.toMatch(/Closure needs|retrospective and Finance/);
  });
});

describe("Tola and Next", () => {
  it('with delivery_agent: its title, the steps with sources, the checked time and Ask Tola (a link, no write)', async () => {
    await open();
    const card = screen.getByRole('complementary', { name: 'Checked where delivery stands' });
    const text = card.textContent!;
    for (const step of fixture().delivery_agent.steps) {
      expect(text).toContain(step.text);
      expect(text).toContain(step.source);
    }
    expect(text).toContain('Checked 12 Apr 09:00');
    expect(within(card).getByRole('link', { name: 'Ask Tola' }).getAttribute('href')).toBe('/assistant');
    expect(calls.map((c) => c.method)).toEqual(['GET']);
  });

  it('without delivery_agent: the summary of agent_summary.text', async () => {
    const body = fixture();
    delete body.delivery_agent;
    respond = () => json(200, body);
    await open();
    expect(screen.queryByRole('complementary', { name: 'Checked where delivery stands' })).toBeNull();
    expect(screen.getByRole('complementary', { name: 'Tola’s summary' }).textContent).toContain('Lagoon Health is moving.');
  });

  it('a malformed delivery_agent falls back to the summary', async () => {
    const body = fixture();
    body.delivery_agent = { agent: 'tola', status: 'done', steps: [{ text: 1 }] };
    respond = () => json(200, body);
    await open();
    expect(screen.getByRole('complementary', { name: 'Tola’s summary' })).toBeTruthy();
  });

  it('Next is plain text with no link', async () => {
    await open();
    const next = screen.getByRole('region', { name: 'Next' });
    expect(next.textContent).toContain(fixture().next);
    expect(within(next).queryAllByRole('link')).toHaveLength(0);
  });
});

describe('sub-nav (Conflicts 5)', () => {
  it('Overview is current and each row is labelled by short_title; only rows with a work id are links', async () => {
    await open();
    const nav = screen.getByRole('navigation', { name: 'Delivery lines' });
    expect([...nav.children].map((c) => c.textContent)).toEqual(['Overview', 'Release', 'Go-live', 'Hypercare', 'Archive', 'Handover', 'Closure']);
    expect(nav.querySelector('[aria-current="page"]')!.textContent).toBe('Overview');
    expect(within(nav).getAllByRole('link').map((a) => [a.textContent, a.getAttribute('href')])).toEqual([
      ['Release', '/work/W-2503'],
      ['Go-live', '/work/W-2510'],
    ]);
  });

  it('falls back to the title when there is no short_title', async () => {
    const body = fixture();
    delete body.delivery[0].short_title;
    respond = () => json(200, body);
    await open();
    expect(within(screen.getByRole('navigation', { name: 'Delivery lines' })).getByRole('link', { name: 'Release gates' })).toBeTruthy();
  });
});

describe('empty and unknown', () => {
  for (const [label, edit] of [
    ['delivery: []', (b: Body) => (b.delivery = [])],
    ['no delivery', (b: Body) => delete b.delivery],
  ] as const) {
    it(`${label} reads "No delivery lines yet." and draws no Tola card`, async () => {
      const body = fixture();
      edit(body);
      delete body.delivery_agent;
      respond = () => json(200, body);
      await open();
      expect(main()).toContain('No delivery lines yet.');
      expect(rows()).toHaveLength(0);
      expect(screen.queryByRole('complementary', { name: 'Checked where delivery stands' })).toBeNull();
    });
  }

  it('an unknown date reads Unknown, and a row without a gate shows an Unknown tag (never blank or 0)', async () => {
    const body = fixture();
    body.delivery[3].at = { unknown: true };
    delete body.delivery[4].gate;
    respond = () => json(200, body);
    await open();
    expect(rows()[3].textContent).toContain('Archived and verified · Unknown');
    expect(tags(rows()[4]).textContent).toMatch(/^Unknown/);
    expect(main()).not.toMatch(/undefined|NaN|\b0\b/);
  });
});

describe('access', () => {
  it('401 signs in back to the delivery path', async () => {
    respond = () => json(401, { code: 'not_signed_in', message: 'Sign in to continue.' });
    await open();
    expect(screen.getByRole('link', { name: 'Sign in' }).getAttribute('href')).toBe('/accounts/login/?next=%2Fprojects%2FP-0101%2Fdelivery');
  });

  for (const status of [403, 404]) {
    it(`${status} shows no title, reference or row`, async () => {
      respond = () => json(status, { code: 'not_found', message: 'We could not find that record.' });
      await open();
      expect(document.body.textContent).toContain('You can’t open this project');
      expect(document.body.textContent).not.toMatch(/Lagoon|REL-0091|Release gates/);
    });
  }

  it('a persona without Projects makes no project call', async () => {
    persona = 'none';
    await open();
    expect(calls).toHaveLength(0);
  });
});
