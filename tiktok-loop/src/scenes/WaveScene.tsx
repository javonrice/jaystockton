import React from 'react';
import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from 'remotion';
import { INDIGO, INDIGO_GLOW, WHITE_DIM, WHITE } from '../theme';
import { DM_SANS } from '../fonts';

// Wave definition
// x: 80 → 1000, centered at y=780, amplitude ±185
// Peak (AM) at x≈280, y=595
// Trough (PM) at x≈800, y=965
const WAVE_PATH = 'M 80,780 C 180,780 210,595 280,595 C 350,595 430,780 540,780 C 650,780 710,965 800,965 C 890,965 950,930 1000,930';

export const TROUGH_X = 800;
export const TROUGH_Y = 965;

export const WaveScene: React.FC<{ dimAt?: number }> = ({ dimAt }) => {
  const frame = useCurrentFrame();
  const DURATION = 230;
  const FADE = 15;

  const sceneOpacity = interpolate(
    frame,
    [0, FADE, DURATION - FADE, DURATION],
    [0, 1, 1, 0],
    { extrapolateRight: 'clamp' },
  );

  // Wave reveal: left to right clip, 0 → 1080 over 60 frames
  const revealX = interpolate(frame, [0, 60], [0, 1080], {
    extrapolateRight: 'clamp',
    easing: Easing.bezier(0.22, 1, 0.36, 1),
  });

  // Labels appear after wave is drawn
  const labelOpacity = interpolate(frame, [65, 85], [0, 1], { extrapolateRight: 'clamp' });

  // Trough pulsing (dim/glow cycle, period ~50 frames, starts at frame 90)
  const pulsePhase = Math.max(0, frame - 90);
  const pulseGlow = 0.5 + 0.5 * Math.sin((pulsePhase / 50) * Math.PI * 2);

  // Dimming for radar handoff
  const waveDim = dimAt !== undefined
    ? interpolate(frame, [dimAt, dimAt + 20], [1, 0.2], { extrapolateRight: 'clamp' })
    : 1;

  return (
    <AbsoluteFill style={{ opacity: sceneOpacity }}>
      <svg width={1080} height={1920} style={{ position: 'absolute', inset: 0 }}>
        <defs>
          <clipPath id="wave-reveal">
            <rect x={0} y={0} width={revealX} height={1920} />
          </clipPath>
        </defs>

        {/* Wave line */}
        <g opacity={waveDim}>
          <path
            d={WAVE_PATH}
            fill="none"
            stroke={INDIGO}
            strokeWidth={4}
            strokeLinecap="round"
            clipPath="url(#wave-reveal)"
            style={{ filter: `drop-shadow(0 0 10px ${INDIGO_GLOW})` }}
          />

          {/* Trough pulsing highlight */}
          <circle
            cx={TROUGH_X} cy={TROUGH_Y} r={interpolate(pulsePhase % 50, [0, 25, 50], [14, 26, 14])}
            fill="none"
            stroke={INDIGO}
            strokeWidth={3}
            opacity={interpolate(frame, [65, 90], [0, 1], { extrapolateRight: 'clamp' }) * (0.4 + 0.5 * pulseGlow)}
          />
          <circle
            cx={TROUGH_X} cy={TROUGH_Y} r={10}
            fill={INDIGO}
            opacity={interpolate(frame, [65, 90], [0, 1], { extrapolateRight: 'clamp' }) * (0.6 + 0.4 * pulseGlow)}
          />
        </g>

        {/* AM label – above peak */}
        <g opacity={labelOpacity * waveDim}>
          <text x={280} y={545} textAnchor="middle" fill={WHITE_DIM} fontSize={36} fontFamily={DM_SANS} fontWeight="500">
            AM
          </text>
          <line x1={280} y1={560} x2={280} y2={590} stroke={WHITE_DIM} strokeWidth={1.5} />
        </g>

        {/* PM label – below trough */}
        <g opacity={labelOpacity * waveDim}>
          <line x1={TROUGH_X} y1={970} x2={TROUGH_X} y2={1000} stroke={INDIGO} strokeWidth={1.5} />
          <text x={TROUGH_X} y={1040} textAnchor="middle" fill={INDIGO} fontSize={36} fontFamily={DM_SANS} fontWeight="500">
            PM
          </text>
          <text x={TROUGH_X} y={1085} textAnchor="middle" fill={WHITE_DIM} fontSize={26} fontFamily={DM_SANS}>
            dopamine lowest
          </text>
        </g>
      </svg>
    </AbsoluteFill>
  );
};
