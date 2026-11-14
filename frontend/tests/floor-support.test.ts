// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from 'vitest';

import { webglAvailable } from '@/features/floor/support';

type Answer = 'context' | null | 'throw';

/** Stubs canvas.getContext: each kind answers with a context (with WEBGL_lose_context), null, or a throw. */
function stubContexts(answers: Record<'webgl2' | 'webgl', Answer>) {
  const lose = vi.fn();
  const getContext = vi.fn((kind: string) => {
    const answer = answers[kind as 'webgl2' | 'webgl'] ?? null;
    if (answer === 'throw') throw new Error('blocked');
    return answer === 'context' ? { getExtension: (name: string) => (name === 'WEBGL_lose_context' ? { loseContext: lose } : null) } : null;
  });
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockImplementation(getContext as unknown as HTMLCanvasElement['getContext']);
  return { getContext, lose };
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe('webglAvailable', () => {
  it('a normal desktop browser with WebGL 2 can show the floor; the test context is released', () => {
    const { getContext, lose } = stubContexts({ webgl2: 'context', webgl: 'context' });
    expect(webglAvailable()).toBe(true);
    expect(getContext).toHaveBeenCalledTimes(1);
    expect(getContext).toHaveBeenCalledWith('webgl2', { failIfMajorPerformanceCaveat: false });
    expect(lose).toHaveBeenCalledTimes(1);
  });

  it('falls back to WebGL 1 when WebGL 2 is missing or throws, without refusing a slow or software GPU', () => {
    for (const webgl2 of [null, 'throw'] as const) {
      const { getContext } = stubContexts({ webgl2, webgl: 'context' });
      expect(webglAvailable()).toBe(true);
      expect(getContext.mock.calls).toEqual([
        ['webgl2', { failIfMajorPerformanceCaveat: false }],
        ['webgl', { failIfMajorPerformanceCaveat: false }],
      ]);
      vi.restoreAllMocks();
    }
  });

  it('is false only when both kinds fail', () => {
    stubContexts({ webgl2: null, webgl: null });
    expect(webglAvailable()).toBe(false);
    stubContexts({ webgl2: 'throw', webgl: 'throw' });
    expect(webglAvailable()).toBe(false);
  });
});
