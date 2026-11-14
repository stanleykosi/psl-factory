'use client';

import { useEffect, useRef } from 'react';

import { FloorScene } from './scene';
import { floorLabel, type FloorProps } from './support';

const HEIGHT = 480;

const cssVar = (name: string) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

/** The 3D factory floor: the same lines, stations and counts as the flat view, drawn with three.js. */
export default function Floor3D({ lines, onFailure }: FloorProps) {
  const host = useRef<HTMLDivElement>(null);
  const floor = useRef<FloorScene | null>(null);
  const canvas = useRef<HTMLCanvasElement | null>(null);
  const failed = useRef(onFailure);
  const latest = useRef(lines);

  useEffect(() => {
    failed.current = onFailure;
    latest.current = lines;
  });

  useEffect(() => {
    // The canvas is made here, not by React, so a remount never reuses a context that was given back.
    const el = document.createElement('canvas');
    el.className = 'overview__floor';
    el.setAttribute('role', 'img');
    el.setAttribute('aria-label', floorLabel(latest.current.length));
    host.current!.appendChild(el);
    canvas.current = el;
    const onLost = (event: Event) => {
      event.preventDefault();
      failed.current();
    };
    el.addEventListener('webglcontextlost', onLost);
    let scene: FloorScene;
    try {
      scene = new FloorScene(el, {
        ink: cssVar('--ink'),
        signal: cssVar('--signal'),
        surface: cssVar('--surface'),
        steel: cssVar('--steel'),
        display: cssVar('--font-display'),
        mono: cssVar('--font-mono'),
      });
    } catch {
      el.removeEventListener('webglcontextlost', onLost);
      el.remove();
      failed.current();
      return;
    }
    floor.current = scene;
    scene.resize(el.clientWidth, HEIGHT);
    scene.update(latest.current);
    const observer = new ResizeObserver(() => scene.resize(el.clientWidth, HEIGHT));
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

  return <div ref={host} />;
}
