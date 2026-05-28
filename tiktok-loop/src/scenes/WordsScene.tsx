import React from 'react';
import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from 'remotion';
import { INDIGO, INDIGO_GLOW, WHITE } from '../theme';
import { SYNE } from '../fonts';

export const WordsScene: React.FC = () => {
  const frame = useCurrentFrame();
  const DURATION = 95;
  const FADE = 12;

  const sceneOpacity = interpolate(
    frame,
    [0, FADE, DURATION - FADE, DURATION],
    [0, 1, 1, 0],
    { extrapolateRight: 'clamp' },
  );

  // WILLPOWER fades in
  const willOpacity = interpolate(frame, [0, 20], [0, 1], { extrapolateRight: 'clamp' });

  // Strikethrough line draws left to right
  const strikeWidth = interpolate(frame, [22, 45], [0, 560], {
    extrapolateRight: 'clamp',
    easing: Easing.bezier(0.22, 1, 0.36, 1),
  });

  // TIMING fades in
  const timingOpacity = interpolate(frame, [48, 65], [0, 1], { extrapolateRight: 'clamp' });

  // TIMING glow pulses
  const timingGlow = 0.7 + 0.3 * Math.sin((frame / 20) * Math.PI);

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
      {/* WILLPOWER + strikethrough */}
      <div style={{ position: 'relative', display: 'inline-block', marginTop: -160 }}>
        <div
          style={{
            fontFamily: SYNE,
            fontWeight: 700,
            fontSize: 108,
            color: WHITE,
            opacity: willOpacity * 0.55,
            letterSpacing: -2,
            lineHeight: 1,
          }}
        >
          WILLPOWER
        </div>
        {/* Strikethrough line */}
        <div
          style={{
            position: 'absolute',
            top: '50%',
            left: '50%',
            transform: 'translate(-50%, -50%)',
            width: strikeWidth,
            height: 6,
            backgroundColor: INDIGO,
            borderRadius: 3,
            boxShadow: `0 0 16px ${INDIGO_GLOW}`,
          }}
        />
      </div>

      {/* TIMING */}
      <div
        style={{
          fontFamily: SYNE,
          fontWeight: 700,
          fontSize: 120,
          color: INDIGO,
          opacity: timingOpacity,
          letterSpacing: -2,
          lineHeight: 1,
          marginTop: 20,
          textShadow: `0 0 ${40 * timingGlow}px ${INDIGO_GLOW}, 0 0 ${80 * timingGlow}px rgba(108,99,255,0.2)`,
        }}
      >
        TIMING
      </div>
    </AbsoluteFill>
  );
};
