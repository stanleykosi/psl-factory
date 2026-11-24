'use client';

import { useEffect, useRef, useState } from 'react';

import { Button } from '@/components';

import { FloorScene, type StationRef } from './scene';
import { StationStrip } from './StationStrip';
import { floorLabel, type FloorProps } from './support';
import './floor.css';

const HINT = 'Point at, tap or tab to a station to read it. Drag sideways to turn the floor; arrow keys turn and tilt, R resets.';

const cssVar = (name: string) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

/** The 3D factory floor (concept 1, the isometric conveyor): the same lines, stations and counts as the flat view. */
export default function Floor3D({ lines, onFailure }: FloorProps) {
  const root = useRef<HTMLDivElement>(null);
  const stage = useRef<HTMLDivElement>(null);
  const overlay = useRef<HTMLDivElement>(null);
  const floor = useRef<FloorScene | null>(null);
  const canvas = useRef<HTMLCanvasElement | null>(null);
  const failed = useRef(onFailure);
  const latest = useRef(lines);
  const [preview, setPreview] = useState<StationRef | null>(null);
  const [pinned, setPinned] = useState<StationRef | null>(null);

  useEffect(() => {
    failed.current = onFailure;
    latest.current = lines;
  });

  useEffect(() => {
    // The stage takes the keys: arrows turn and tilt, R resets. Set here because it is a tab stop on a plain group.
    const el = stage.current!;
    const turns: Record<string, [number, number]> = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, 1], ArrowDown: [0, -1] };
    const onKey = (event: KeyboardEvent) => {
      if (event.target !== el) return;
      if (turns[event.key]) floor.current?.turn(...turns[event.key]);
      else if (event.key === 'r' || event.key === 'R') floor.current?.reset();
      else return;
      event.preventDefault();
    };
    el.tabIndex = 0;
    el.addEventListener('keydown', onKey);
    return () => el.removeEventListener('keydown', onKey);
  }, []);

  useEffect(() => {
    // The canvas is made here, not by React, so a remount never reuses a context that was given back.
    const el = document.createElement('canvas');
    el.className = 'overview__floor';
    el.setAttribute('role', 'img');
    el.setAttribute('aria-label', floorLabel(latest.current.length));
    stage.current!.insertBefore(el, overlay.current);
    canvas.current = el;
    const onLost = (event: Event) => {
      event.preventDefault();
      failed.current();
    };
    el.addEventListener('webglcontextlost', onLost);
    let scene: FloorScene;
    try {
      scene = new FloorScene(
        el,
        overlay.current!,
        {
          ink: cssVar('--ink'),
          belt: cssVar('--ink-strong'),
          signal: cssVar('--signal'),
          signalTint: cssVar('--signal-tint'),
          surface: cssVar('--surface'),
          board: cssVar('--surface-subtle'),
          plate: cssVar('--neutral-tint'),
          muted: cssVar('--nav-muted'),
          focus: cssVar('--focus'),
        },
        { onPreview: setPreview, onPin: setPinned },
      );
    } catch {
      el.removeEventListener('webglcontextlost', onLost);
      el.remove();
      failed.current();
      return;
    }
    floor.current = scene;
    scene.resize(el.clientWidth, el.clientHeight);
    scene.update(latest.current);
    const observer = new ResizeObserver(() => scene.resize(el.clientWidth, el.clientHeight));
    observer.observe(el);
    return () => {
      observer.disconnect();
      el.removeEventListener('webglcontextlost', onLost);
      scene.dispose();
      el.remove();
      floor.current = null;
      canvas.current = null;
    };
  }, []);

  useEffect(() => {
    canvas.current?.setAttribute('aria-label', floorLabel(lines.length));
    floor.current?.update(lines);
  }, [lines]);

  useEffect(() => {
    floor.current?.setPinned(pinned);
  }, [pinned]);

  // The strip follows the pinned station, else the one under the pointer or focus; a station that left the floor lets go.
  const shown = pinned ?? preview;
  const shownLine = shown ? lines.find((l) => l.key === shown.line) : undefined;
  const found = shownLine?.stations.find((s) => s.name === shown?.name);
  if (pinned && !lines.some((l) => l.key === pinned.line && l.stations.some((s) => s.name === pinned.name))) setPinned(null);

  // Esc from the floor or the strip lets go of a pinned station.
  useEffect(() => {
    if (!pinned) return;
    const el = root.current!;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setPinned(null);
    };
    el.addEventListener('keydown', onKey);
    return () => el.removeEventListener('keydown', onKey);
  }, [pinned]);

  return (
    <div ref={root} className="floor">
      <div ref={stage} className="floor__stage" role="group" aria-label="3D floor view. Arrow keys turn and tilt, R resets.">
        <div ref={overlay} className="floor__labels" />
      </div>
      <div className="floor__bar">
        {shownLine && found ? (
          <StationStrip title={shownLine.title} lineKey={shownLine.key} station={found} pinned={pinned !== null} onUnpin={() => setPinned(null)} />
        ) : (
          <p className="floor__readout">{HINT}</p>
        )}
        <Button kind="secondary" onClick={() => floor.current?.reset()}>
          Reset view
        </Button>
      </div>
    </div>
  );
}
