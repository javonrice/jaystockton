import React from 'react';
import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from 'remotion';
import { INDIGO, INDIGO_GLOW, WHITE } from '../theme';
import { SYNE, DM_SANS } from '../fonts';
import { TROUGH_X, TROUGH_Y } from './WaveScene';

const WAVE_PATH = 'M 80,780 C 180,780 210,595 280,595 C 350,595 430,780 540,780 C 650,780 710,965 800,965 C 890,965 950,930 1000,930';

// Rectangle around the trough area
const BOX = { x: 680, y: 890, w: 260, h: 160 };

export const WindowScene: React.FC = () => {
  const frame = useCurrentFrame();
  const DURATION = 95;
  const FADE = 12;

  const sceneOpacity = interpolate(
    frame,
    [0, FADE, DURATION - FADE, DURATION],
    [0, 1, 1, 0],
    { extrapolateRight: 'clamp' },
  );

  // Wave fades back in
  const waveOpacity = interpolate(frame, [0, 20], [0, 0.6], { extrapolateRight: 'clamp' });

  // Box draws: perimeter stroke-dasharray trick
  // Perimeter = 2*(260+160) = 840
  const PERIMETER = 2 * (BOX.w + BOX.h);
  const boxProgress = interpolate(frame, [22, 55], [0, 1], {
    extrapolateRight: 'clamp',
    easing: Easing.bezier(0.22, 1, 0.36, 1),
  });
  const boxDash = PERIMETER * boxProgress;

  // Text inside box
  const textOpacity = interpolate(frame, [58, 72], [0, 1], { extrapolateRight: 'clamp' });

  return (
    <AbsoluteFill style={{ opacity: sceneOpacity }}>
      <svg width={1080} height={1920} style={{ position: 'absolute', inset: 0 }}>
        {/* Dimmed wave background */}
        <path
          d={WAVE_PATH}
          fill="none"
          stroke={INDIGO}
          strokeWidth={3}
          opacity={waveOpacity}
        />

        {/* Trough dot */}
        <circle cx={TROUGH_X} cy={TROUGH_Y} r={8} fill={INDIGO} opacity={waveOpacity} />

        {/* Animated rectangle */}
        <rect
          x={BOX.x} y={BOX.y}
          width={BOX.w} height={BOX.h}
          fill="rgba(108, 99, 255, 0.08)"
          stroke={INDIGO}
          strokeWidth={3}
          rx={6}
          strokeDasharray={PERIMETER}
          strokeDashoffset={PERIMETER - boxDash}
          style={{ filter: `drop-shadow(0 0 8px ${INDIGO_GLOW})` }}
        />

        {/* YOUR WINDOW label */}
        <text
          x={BOX.x + BOX.w / 2}
          y={BOX.y + BOX.h / 2 - 8}
          textAnchor="middle"
          dominantBaseline="middle"
          fill={WHITE}
          fontSize={26}
          fontFamily={SYNE}
          fontWeight="700"
          opacity={textOpacity}
          letterSpacing={2}
        >
          YOUR
        </text>
        <text
          x={BOX.x + BOX.w / 2}
          y={BOX.y + BOX.h / 2 + 22}
          textAnchor="middle"
          dominantBaseline="middle"
          fill={INDIGO}
          fontSize={26}
          fontFamily={SYNE}
          fontWeight="700"
          opacity={textOpacity}
          letterSpacing={2}
          style={{ filter: `drop-shadow(0 0 6px ${INDIGO_GLOW})` }}
        >
          WINDOW
        </text>
      </svg>
    </AbsoluteFill>
  );
};
