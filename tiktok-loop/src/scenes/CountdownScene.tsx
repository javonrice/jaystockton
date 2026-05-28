import React from 'react';
import { AbsoluteFill, interpolateColors, spring, useCurrentFrame, useVideoConfig } from 'remotion';
import { COLD_BLUE, INDIGO, RED_PURPLE, WHITE, WHITE_DIM } from '../theme';
import { SYNE, DM_SANS } from '../fonts';
import { interpolate } from 'remotion';

const pad = (n: number) => String(Math.floor(n)).padStart(2, '0');

// Hourglass particles (seeded)
const PARTICLES = Array.from({ length: 12 }, (_, i) => {
  const s = (i * 2311 + 17) % 1000;
  return {
    x: 200 + (s % 680),
    speed: 1.2 + (s % 8) / 5,
    phase: (s % 100) / 100,
  };
});

export const CountdownScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const DURATION = 140;
  const FADE = 15;
  const COUNT_START = FADE;
  const COUNT_END = DURATION - FADE;
  const TOTAL_SECONDS = 240;

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

  // Spring tick on each displayed second
  const displaySecond = Math.floor(remaining);
  const secondFrac = remaining - displaySecond;
  const tickF = (1 - secondFrac) * 8;
  const tickScale = spring({ frame: tickF, fps, config: { damping: 6, stiffness: 300 }, from: 1.08, to: 1 });

  // Color drain: RED_PURPLE → INDIGO → COLD_BLUE
  const urgencyColor = interpolateColors(progress, [0, 0.5, 1], [RED_PURPLE, INDIGO, COLD_BLUE]);

  // Label color: WHITE_DIM → COLD_BLUE
  const labelColor = interpolateColors(progress, [0, 0.7, 1], [WHITE_DIM, WHITE_DIM, COLD_BLUE]);

  // "THE WINDOW" label spring entry
  const labelY = spring({ frame: Math.max(0, frame - FADE), fps, config: { damping: 14, stiffness: 180 }, from: 30, to: 0 });

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
      {/* Hourglass particles falling */}
      <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none' }}>
        <svg width={1080} height={1920} style={{ position: 'absolute', inset: 0 }}>
          {PARTICLES.map((p, i) => {
            const startY = -20 + p.phase * 1920;
            const y = ((startY + frame * p.speed * 3) % 1920 + 1920) % 1920;
            const pulseOp = 0.15 + 0.1 * Math.sin(frame / 12 + p.phase * 6.28);
            return <circle key={i} cx={p.x} cy={y} r={2} fill={COLD_BLUE} opacity={pulseOp} />;
          })}
        </svg>
      </div>

      {/* Timer */}
      <div
        style={{
          fontFamily: SYNE,
          fontSize: 140,
          fontWeight: 700,
          color: WHITE,
          letterSpacing: -4,
          transform: `scale(${tickScale})`,
          textShadow: `0 0 60px ${urgencyColor}, 0 0 120px ${urgencyColor}40`,
          marginTop: -180,
          willChange: 'transform',
        }}
      >
        {pad(minutes)}:{pad(seconds)}
      </div>

      {/* THE WINDOW label */}
      <div
        style={{
          fontFamily: DM_SANS,
          fontSize: 36,
          color: labelColor,
          letterSpacing: 4,
          textTransform: 'uppercase',
          marginTop: 8,
          transform: `translateY(${labelY}px)`,
          willChange: 'transform',
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
            backgroundColor: urgencyColor,
            borderRadius: 2,
            boxShadow: `0 0 12px ${urgencyColor}`,
            transition: 'none',
          }}
        />
      </div>
    </AbsoluteFill>
  );
};
