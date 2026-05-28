import React from 'react';
import { AbsoluteFill, interpolate, useCurrentFrame } from 'remotion';
import { INDIGO, INDIGO_GLOW, WHITE, WHITE_DIM } from '../theme';
import { SYNE, DM_SANS } from '../fonts';

export const CTAScene: React.FC = () => {
  const frame = useCurrentFrame();
  const DURATION = 145;

  const sceneOpacity = interpolate(
    frame,
    [0, 12, DURATION - 18, DURATION],
    [0, 1, 1, 0],
    { extrapolateRight: 'clamp' },
  );

  const line1Opacity = interpolate(frame, [0, 14], [0, 1], { extrapolateRight: 'clamp' });
  const urlOpacity  = interpolate(frame, [10, 26], [0, 1], { extrapolateRight: 'clamp' });
  const line3Opacity = interpolate(frame, [22, 36], [0, 1], { extrapolateRight: 'clamp' });

  // seeyourloop.com scales up on entry
  const urlScale = interpolate(frame, [10, 28], [0.82, 1], {
    extrapolateRight: 'clamp',
  });

  // subtle glow pulse on the URL after it lands
  const glowPulse = 0.7 + 0.3 * Math.sin((Math.max(0, frame - 28) / 22) * Math.PI);

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
          marginBottom: 20,
          marginTop: -80,
          textAlign: 'center',
        }}
      >
        I built something for that.
      </div>

      <div
        style={{
          fontFamily: SYNE,
          fontWeight: 700,
          fontSize: 96,
          color: WHITE,
          opacity: urlOpacity,
          letterSpacing: -2,
          lineHeight: 1,
          transform: `scale(${urlScale})`,
          textShadow: `0 0 ${60 * glowPulse}px rgba(108,99,255,0.5), 0 0 ${120 * glowPulse}px rgba(108,99,255,0.2)`,
          textAlign: 'center',
        }}
      >
        seeyourloop.com
      </div>

      <div
        style={{
          fontFamily: DM_SANS,
          fontSize: 42,
          color: INDIGO,
          opacity: line3Opacity,
          marginTop: 20,
          letterSpacing: 1,
          textShadow: `0 0 20px ${INDIGO_GLOW}`,
        }}
      >
        Link in bio.
      </div>
    </AbsoluteFill>
  );
};
