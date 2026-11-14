import { afterEach } from 'vitest';

if (typeof window !== 'undefined') {
  // jsdom has no fetch API, so Node's Request is used; give it the browser's behaviour of
  // resolving same-origin paths such as /api/v1/me against the page URL.
  const NodeRequest = globalThis.Request;
  class PageRequest extends NodeRequest {
    constructor(input: RequestInfo | URL, init?: RequestInit) {
      super(typeof input === 'string' ? new URL(input, window.location.href) : input, init);
    }
  }
  globalThis.Request = PageRequest as typeof Request;

  const { cleanup } = await import('@testing-library/react');
  afterEach(() => cleanup());
}
