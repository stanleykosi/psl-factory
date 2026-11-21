'use client';

import { createElement } from 'react';
import Script from 'next/script';

/** Links outside this desk open the existing signed-in form on the factory host. */
export function FactoryDesk({ pathname, destinations }: {
  pathname: string;
  destinations: {key: string; title: string; django_url: string}[];
}) {
  const origin = process.env.NEXT_PUBLIC_FACTORY_ORIGIN;
  const item = destinations.find(destination => destination.key === pathname.split('/')[1]);
  const desk = pathname === '/' || pathname === '/my-work' || /^\/work\/\d+(\/(history|decide))?\/?$/.test(pathname);
  if (!desk) return <main className="shell-main">
    <h1>{item?.title || 'Factory sections'}</h1>
    <nav aria-label="Factory sections">{destinations.map(section => <p key={section.key}>
      <a href={section.key === 'my_work' ? '/my-work' : (origin ? new URL(section.django_url, origin).href : '/factory-forms' + section.django_url)}>{section.title}</a>
    </p>)}</nav>
  </main>;
  return <main className="shell-main">
    {createElement('psl-work-client', { 'factory-origin': origin, 'form-prefix': origin ? '' : '/factory-forms',
      'desk-path': '/my-work' }, 'Loading your work…')}
    <Script src="/factory-assets/work-client.js" strategy="afterInteractive" />
  </main>;
}
