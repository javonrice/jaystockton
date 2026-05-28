import React from 'react';
import { spring, useCurrentFrame, useVideoConfig } from 'remotion';

export type KineticMode = 'slam-down' | 'rise-up' | 'scale-in' | 'slide-left';

interface KineticTextProps {
  startFrame: number;
  mode: KineticMode;
  children: React.ReactNode;
  style?: React.CSSProperties;
}

export const KineticText: React.FC<KineticTextProps> = ({ startFrame, mode, children, style }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const f = Math.max(0, frame - startFrame);

  let transform = '';
  let opacity = 1;

  if (mode === 'slam-down') {
    const y = spring({ frame: f, fps, config: { damping: 8, stiffness: 200 }, from: -80, to: 0 });
    const s = spring({ frame: f, fps, config: { damping: 8, stiffness: 200 }, from: 1.15, to: 1 });
    transform = `translateY(${y}px) scale(${s})`;
    opacity = f < 2 ? 0 : 1;
  } else if (mode === 'rise-up') {
    const y = spring({ frame: f, fps, config: { damping: 14, stiffness: 180 }, from: 40, to: 0 });
    transform = `translateY(${y}px)`;
    opacity = f < 2 ? 0 : 1;
  } else if (mode === 'scale-in') {
    const s = spring({ frame: f, fps, config: { damping: 12, stiffness: 220 }, from: 0, to: 1 });
    transform = `scale(${s})`;
    opacity = f < 1 ? 0 : 1;
  } else if (mode === 'slide-left') {
    const x = spring({ frame: f, fps, config: { damping: 14, stiffness: 160 }, from: 60, to: 0 });
    transform = `translateX(${x}px)`;
    opacity = f < 2 ? 0 : 1;
  }

  if (frame < startFrame) {
    opacity = 0;
    transform = '';
  }

  return (
    <div style={{ display: 'contents', ...style }}>
      <div style={{ transform, opacity, willChange: 'transform, opacity' }}>
        {children}
      </div>
    </div>
  );
};
