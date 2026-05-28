import React from 'react';
import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from 'remotion';
import { INDIGO, INDIGO_GLOW, WHITE_DIM } from '../theme';
import { TROUGH_X, TROUGH_Y } from './WaveScene';
import { DM_SANS } from '../fonts';

// 8 radar lines at different angles from the trough
const LINES = [
  { angle: -80, bright: false },
  { angle: -55, bright: false },
  { angle: -30, bright: true },  // the bright one
  { angle: -5,  bright: false },
  { angle: 20,  bright: false },
  { angle: 45,  bright: false },
  { angle: 70,  bright: false },
  { angle: 100, bright: false },
];

const LINE_LEN = 320;

export const RadarScene: React.FC = () => {
  const frame = useCurrentFrame();
  const DURATION = 160;
  const FADE = 15;
  const SHOOT_START = 20; // local frame when lines start shooting
  const SHOOT_DUR = 40;

  const sceneOpacity = interpolate(
    frame,
    [0, FADE, DURATION - FADE, DURATION],
    [0, 1, 1, 0],
    { extrapolateRight: 'clamp' },
  );

  // Wave dims in background – handled by WaveScene dimAt prop, but we also show a dim wave here
  const bgWaveOpacity = interpolate(frame, [0, FADE], [0, 0.2], { extrapolateRight: 'clamp' });

  // Each line shoots out
  const shootProgress = interpolate(
    frame,
    [SHOOT_START, SHOOT_START + SHOOT_DUR],
    [0, 1],
    { extrapolateRight: 'clamp', easing: Easing.bezier(0.22, 1, 0.36, 1) },
  );

  // Scanning flicker on bright line
  const scanFlicker = 0.6 + 0.4 * Math.sin((frame / 8) * Math.PI);

  // "Brain scanning" text fades in
  const textOpacity = interpolate(frame, [60, 80], [0, 1], { extrapolateRight: 'clamp' });

  return (
    <AbsoluteFill style={{ opacity: sceneOpacity }}>
      <svg width={1080} height={1920} style={{ position: 'absolute', inset: 0 }}>
        {/* Origin dot */}
        <circle
          cx={TROUGH_X} cy={TROUGH_Y} r={10}
          fill={INDIGO}
          opacity={interpolate(frame, [0, FADE], [0, 1], { extrapolateRight: 'clamp' })}
          style={{ filter: `drop-shadow(0 0 8px ${INDIGO_GLOW})` }}
        />

        {/* Radar lines */}
        {LINES.map(({ angle, bright }, i) => {
          const rad = (angle * Math.PI) / 180;
          const ex = TROUGH_X + LINE_LEN * Math.cos(rad);
          const ey = TROUGH_Y + LINE_LEN * Math.sin(rad);
          const opacity = bright ? scanFlicker : 0.3;
          const len = shootProgress * LINE_LEN;
          const lx = TROUGH_X + len * Math.cos(rad);
          const ly = TROUGH_Y + len * Math.sin(rad);

          return (
            <g key={i}>
              <line
                x1={TROUGH_X} y1={TROUGH_Y}
                x2={lx} y2={ly}
                stroke={bright ? INDIGO : WHITE_DIM}
                strokeWidth={bright ? 3 : 1.5}
                opacity={opacity}
                style={bright ? { filter: `drop-shadow(0 0 6px ${INDIGO_GLOW})` } : undefined}
              />
              {/* Tip dot on bright line */}
              {bright && shootProgress > 0.5 && (
                <circle
                  cx={lx} cy={ly} r={5}
                  fill={INDIGO}
                  opacity={scanFlicker * 0.9}
                />
              )}
            </g>
          );
        })}

        {/* Scan ring */}
        <circle
          cx={TROUGH_X} cy={TROUGH_Y}
          r={interpolate(frame, [SHOOT_START, SHOOT_START + SHOOT_DUR], [0, LINE_LEN], { extrapolateRight: 'clamp' })}
          fill="none"
          stroke={INDIGO}
          strokeWidth={1}
          opacity={interpolate(frame, [SHOOT_START, SHOOT_START + 10, SHOOT_START + SHOOT_DUR], [0, 0.4, 0], { extrapolateRight: 'clamp' })}
        />

        {/* Label */}
        <text
          x={540} y={1200}
          textAnchor="middle"
          fill={WHITE_DIM}
          fontSize={34}
          fontFamily={DM_SANS}
          opacity={textOpacity}
        >
          scanning for the fastest option
        </text>
      </svg>
    </AbsoluteFill>
  );
};
