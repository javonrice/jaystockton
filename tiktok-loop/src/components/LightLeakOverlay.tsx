import React from 'react';
import { AbsoluteFill, interpolate, useCurrentFrame } from 'remotion';

type Corner = 'top-left' | 'top-right' | 'center';
type ColorHint = 'gold' | 'white' | 'cold-blue' | 'red-purple';

interface LightLeakOverlayProps {
  corner?: Corner;
  colorHint?: ColorHint;
  durationInFrames?: number;
}

const COLOR_MAP: Record<ColorHint, string> = {
  gold: 'rgba(245, 200, 66, 0.85)',
  white: 'rgba(255, 255, 255, 0.9)',
  'cold-blue': 'rgba(26, 143, 255, 0.8)',
  'red-purple': 'rgba(192, 63, 192, 0.8)',
};

const CORNER_POS: Record<Corner, { x: string; y: string }> = {
  'top-left': { x: '10%', y: '8%' },
  'top-right': { x: '90%', y: '8%' },
  center: { x: '50%', y: '40%' },
};

export const LightLeakOverlay: React.FC<LightLeakOverlayProps> = ({
  corner = 'top-right',
  colorHint = 'white',
  durationInFrames = 20,
}) => {
  const frame = useCurrentFrame();
  const mid = Math.floor(durationInFrames * 0.3);
  const opacity = interpolate(
    frame,
    [0, mid, durationInFrames - 4, durationInFrames],
    [0, 0.4, 0.4, 0],
    { extrapolateRight: 'clamp' },
  );

  const { x, y } = CORNER_POS[corner];
  const color = COLOR_MAP[colorHint];

  return (
    <AbsoluteFill
      style={{
        pointerEvents: 'none',
        mixBlendMode: 'screen',
        opacity,
        background: `radial-gradient(ellipse 60% 40% at ${x} ${y}, ${color}, transparent 70%)`,
      }}
    />
  );
};
