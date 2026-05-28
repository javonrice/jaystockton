import React from 'react';
import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from 'remotion';
import { GOLD, INDIGO, INDIGO_GLOW, WHITE_DIM } from '../theme';
import { SYNE, DM_SANS } from '../fonts';

const EMBERS = Array.from({ length: 8 }, (_, i) => {
  const s = (i * 1973 + 42) % 1000;
  return {
    x: 340 + (s % 400),
    baseY: 980 + (s % 120),
    speed: 0.8 + (s % 12) / 10,
    amp: 8 + (s % 16),
    freq: 30 + (s % 20),
    phase: (s % 62) / 10,
    baseOpacity: 0.2 + (s % 20) / 100,
  };
});

export const CTAScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const DURATION = 145;

  const sceneOpacity = interpolate(
    frame,
    [0, 12, DURATION - 18, DURATION],
    [0, 1, 1, 0],
    { extrapolateRight: 'clamp' },
  );

  // Line 1: typewriter reveal
  const LINE1 = 'I built something for that.';
  const typeProgress = interpolate(frame, [0, 30], [0, 1], { extrapolateRight: 'clamp' });
  const visibleChars = Math.floor(typeProgress * LINE1.length);
  const displayLine1 = LINE1.slice(0, visibleChars);
  const cursor = frame >= 1 && frame < 45 && frame % 16 < 8 ? '|' : '';

  // seeyourloop.com — spring scale entry (gold glow)
  const urlFrame = Math.max(0, frame - 10);
  const urlScale = spring({ frame: urlFrame, fps, config: { damping: 10, stiffness: 220 }, from: 0.7, to: 1 });
  const urlOpacity = frame >= 10 ? 1 : 0;
  const glowPulse = 0.75 + 0.25 * Math.sin(((Math.max(0, frame - 28)) / 18) * Math.PI);

  // "Link in bio." — spring rise-up
  const bioFrame = Math.max(0, frame - 22);
  const bioY = spring({ frame: bioFrame, fps, config: { damping: 14, stiffness: 180 }, from: 30, to: 0 });
  const bioOpacity = frame >= 22 ? 1 : 0;

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
      {/* Ember particles */}
      <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none' }}>
        <svg width={1080} height={1920} style={{ position: 'absolute', inset: 0 }}>
          {EMBERS.map((e, i) => {
            const dy = (frame * e.speed) % 300;
            const dx = Math.sin(frame / e.freq + e.phase) * e.amp;
            const op = e.baseOpacity * interpolate(dy, [0, 60, 240, 300], [0, 1, 1, 0], { extrapolateRight: 'clamp' });
            return <circle key={i} cx={e.x + dx} cy={e.baseY - dy} r={2} fill={GOLD} opacity={op} />;
          })}
        </svg>
      </div>

      {/* "I built something for that." */}
      <div
        style={{
          fontFamily: DM_SANS,
          fontSize: 44,
          color: WHITE_DIM,
          marginBottom: 20,
          marginTop: -80,
          textAlign: 'center',
          letterSpacing: 0.5,
        }}
      >
        {displayLine1}{cursor}
      </div>

      {/* seeyourloop.com — gold glow */}
      <div
        style={{
          fontFamily: SYNE,
          fontWeight: 700,
          fontSize: 96,
          color: '#FFFFFF',
          opacity: urlOpacity,
          letterSpacing: -2,
          lineHeight: 1,
          transform: `scale(${urlScale})`,
          textShadow: [
            `0 0 ${40 * glowPulse}px rgba(245,200,66,0.8)`,
            `0 0 ${80 * glowPulse}px rgba(245,200,66,0.4)`,
            `0 0 ${140 * glowPulse}px rgba(245,200,66,0.15)`,
          ].join(', '),
          textAlign: 'center',
          willChange: 'transform',
        }}
      >
        seeyourloop.com
      </div>

      {/* Link in bio. */}
      <div
        style={{
          fontFamily: DM_SANS,
          fontSize: 42,
          color: INDIGO,
          opacity: bioOpacity,
          marginTop: 22,
          letterSpacing: 6,
          transform: `translateY(${bioY}px)`,
          textShadow: `0 0 20px ${INDIGO_GLOW}`,
          willChange: 'transform',
        }}
      >
        Link in bio.
      </div>
    </AbsoluteFill>
  );
};
