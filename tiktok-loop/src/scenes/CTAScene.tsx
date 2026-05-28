import React from 'react';
import { AbsoluteFill, interpolate, useCurrentFrame } from 'remotion';
import { INDIGO, INDIGO_GLOW, WHITE, WHITE_DIM } from '../theme';
import { SYNE, DM_SANS } from '../fonts';

export const CTAScene: React.FC = () => {
  const frame = useCurrentFrame();
  const DURATION = 45;

  const sceneOpacity = interpolate(
    frame,
    [0, 10, DURATION - 12, DURATION],
    [0, 1, 1, 0],
    { extrapolateRight: 'clamp' },
  );

  const line1Opacity = interpolate(frame, [0, 12], [0, 1], { extrapolateRight: 'clamp' });
  const loopOpacity = interpolate(frame, [8, 20], [0, 1], { extrapolateRight: 'clamp' });
  const line3Opacity = interpolate(frame, [16, 28], [0, 1], { extrapolateRight: 'clamp' });

  // LOOP slight scale-in
  const loopScale = interpolate(frame, [8, 22], [0.85, 1], {
    extrapolateRight: 'clamp',
  });

  return (
    <AbsoluteFill
      style={{
        opacity: sceneOpacity,
        alignItems: 'center',
        justifyContent: 'center',
        flexDirection: 'column',
        gap: 0,
      }}
    >
      <div
        style={{
          fontFamily: DM_SANS,
          fontSize: 44,
          color: WHITE_DIM,
          opacity: line1Opacity,
          marginBottom: 8,
          marginTop: -60,
          textAlign: 'center',
        }}
      >
        I built something for that.
      </div>

      <div
        style={{
          fontFamily: SYNE,
          fontWeight: 700,
          fontSize: 180,
          color: WHITE,
          opacity: loopOpacity,
          letterSpacing: -6,
          lineHeight: 0.9,
          transform: `scale(${loopScale})`,
          textShadow: `0 0 80px rgba(108,99,255,0.4)`,
        }}
      >
        LOOP
      </div>

      <div
        style={{
          fontFamily: DM_SANS,
          fontSize: 42,
          color: INDIGO,
          opacity: line3Opacity,
          marginTop: 16,
          letterSpacing: 1,
          textShadow: `0 0 20px ${INDIGO_GLOW}`,
        }}
      >
        Link in bio.
      </div>
    </AbsoluteFill>
  );
};
