import React from 'react';
import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from 'remotion';
import { INDIGO, WHITE } from '../theme';
import { SYNE, DM_SANS } from '../fonts';

const pad = (n: number) => String(Math.floor(n)).padStart(2, '0');

export const CountdownScene: React.FC = () => {
  const frame = useCurrentFrame();
  const DURATION = 140;
  const FADE = 15;
  const COUNT_START = FADE;
  const COUNT_END = DURATION - FADE;
  const TOTAL_SECONDS = 240; // 4 minutes = 240 seconds

  const sceneOpacity = interpolate(
    frame,
    [0, FADE, DURATION - FADE, DURATION],
    [0, 1, 1, 0],
    { extrapolateRight: 'clamp' },
  );

  const progress = interpolate(frame, [COUNT_START, COUNT_END], [0, 1], {
    extrapolateRight: 'clamp',
  });

  const remaining = TOTAL_SECONDS * (1 - progress);
  const minutes = Math.floor(remaining / 60);
  const seconds = remaining % 60;

  // Pulse on each "second" of displayed time
  const displaySecond = Math.floor(remaining);
  const secondFrac = remaining - displaySecond;
  const tickScale = 1 + interpolate(secondFrac, [0.9, 1], [0, 0.06], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.bezier(0.34, 1.56, 0.64, 1),
  });

  return (
    <AbsoluteFill
      style={{
        opacity: sceneOpacity,
        alignItems: 'center',
        justifyContent: 'center',
        flexDirection: 'column',
        gap: 24,
      }}
    >
      <div
        style={{
          fontFamily: SYNE,
          fontSize: 140,
          fontWeight: 700,
          color: WHITE,
          letterSpacing: -4,
          transform: `scale(${tickScale})`,
          textShadow: `0 0 60px rgba(108, 99, 255, 0.35)`,
          marginTop: -180,
        }}
      >
        {pad(minutes)}:{pad(seconds)}
      </div>

      <div
        style={{
          fontFamily: DM_SANS,
          fontSize: 36,
          color: 'rgba(255,255,255,0.45)',
          letterSpacing: 4,
          textTransform: 'uppercase',
          marginTop: 8,
        }}
      >
        the window
      </div>

      {/* Progress bar */}
      <div
        style={{
          width: 480,
          height: 3,
          backgroundColor: 'rgba(255,255,255,0.12)',
          borderRadius: 2,
          marginTop: 24,
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            width: `${(1 - progress) * 100}%`,
            height: '100%',
            backgroundColor: INDIGO,
            borderRadius: 2,
            boxShadow: `0 0 12px ${INDIGO}`,
          }}
        />
      </div>
    </AbsoluteFill>
  );
};
