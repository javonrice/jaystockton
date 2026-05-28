import React from 'react';
import { AbsoluteFill, interpolate, useCurrentFrame } from 'remotion';
import { WHITE } from '../theme';

export const DotScene: React.FC = () => {
  const frame = useCurrentFrame();
  const DURATION = 95;
  const FADE = 15;

  const sceneOpacity = interpolate(
    frame,
    [0, FADE, DURATION - FADE, DURATION],
    [0, 1, 1, 0],
    { extrapolateRight: 'clamp' },
  );

  // Pulse: scale between 1 and 1.4, opacity 0.6 to 1, period ~40 frames
  const pulseT = (frame % 40) / 40;
  const pulseScale = 1 + 0.35 * Math.sin(pulseT * Math.PI * 2);
  const pulseOpacity = 0.65 + 0.35 * Math.sin(pulseT * Math.PI * 2);

  const dotAppear = interpolate(frame, [0, FADE], [0, 1], { extrapolateRight: 'clamp' });

  return (
    <AbsoluteFill
      style={{
        opacity: sceneOpacity,
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      <div
        style={{
          width: 24,
          height: 24,
          borderRadius: '50%',
          backgroundColor: WHITE,
          transform: `scale(${pulseScale})`,
          opacity: dotAppear * pulseOpacity,
          boxShadow: `0 0 ${20 * pulseScale}px ${8 * pulseScale}px rgba(255,255,255,0.3)`,
          marginTop: -200, // nudge up from true center
        }}
      />
    </AbsoluteFill>
  );
};
