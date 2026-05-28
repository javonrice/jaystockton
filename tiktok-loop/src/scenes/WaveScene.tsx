import React from 'react';
import { AbsoluteFill, Easing, interpolate, spring, useCurrentFrame, useVideoConfig } from 'remotion';
import { COLD_BLUE, COLD_BLUE_GLOW, GOLD, INDIGO, WHITE_DIM } from '../theme';
import { DM_SANS } from '../fonts';
import { WAVE_PATH, TROUGH_X, TROUGH_Y, PEAK_X, PEAK_Y } from '../waveGeometry';

export { TROUGH_X, TROUGH_Y };

const RING_OFFSETS = [0, 14, 28];

export const WaveScene: React.FC<{ dimAt?: number }> = ({ dimAt }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const DURATION = 230;
  const FADE = 15;

  const sceneOpacity = interpolate(
    frame,
    [0, FADE, DURATION - FADE, DURATION],
    [0, 1, 1, 0],
    { extrapolateRight: 'clamp' },
  );

  // Wave reveal: left-to-right clip over 60 frames
  const revealX = interpolate(frame, [0, 60], [0, 1080], {
    extrapolateRight: 'clamp',
    easing: Easing.bezier(0.22, 1, 0.36, 1),
  });

  // Labels: spring entries after wave is drawn
  const amSpringY = spring({ frame: Math.max(0, frame - 65), fps, config: { damping: 14, stiffness: 180 }, from: 40, to: 0 });
  const amOpacity = frame >= 65 ? 1 : 0;

  const pmSpringY = spring({ frame: Math.max(0, frame - 65), fps, config: { damping: 8, stiffness: 200 }, from: -60, to: 0 });
  const pmOpacity = frame >= 65 ? 1 : 0;

  // Trough breathing after draw
  const troughDy = frame >= 90 ? 4 * Math.sin(((frame - 90) / 25) * Math.PI) : 0;
  const troughY = TROUGH_Y + troughDy;

  // Trough pulse for rings (starts frame 90, period 45 frames)
  const pulsePhase = Math.max(0, frame - 90);

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
          {/* Gold → White → ColdBlue gradient along wave */}
          <linearGradient id="wave-gradient" x1="80" y1="0" x2="1000" y2="0" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stopColor={GOLD} />
            <stop offset="35%" stopColor="#FFFFFF" stopOpacity={0.85} />
            <stop offset="100%" stopColor={COLD_BLUE} />
          </linearGradient>
        </defs>

        <g opacity={waveDim}>
          {/* Wave line with gradient */}
          <path
            d={WAVE_PATH}
            fill="none"
            stroke="url(#wave-gradient)"
            strokeWidth={4}
            strokeLinecap="round"
            clipPath="url(#wave-reveal)"
            style={{ filter: `drop-shadow(0 0 10px ${INDIGO})` }}
          />

          {/* Peak glow dot */}
          <circle
            cx={PEAK_X} cy={PEAK_Y} r={8}
            fill={GOLD}
            opacity={interpolate(frame, [55, 75], [0, 0.8], { extrapolateRight: 'clamp' })}
            style={{ filter: `drop-shadow(0 0 12px rgba(245,200,66,0.6))` }}
          />

          {/* Trough dot — breathes with COLD_BLUE */}
          <circle
            cx={TROUGH_X} cy={troughY} r={10}
            fill={COLD_BLUE}
            opacity={interpolate(frame, [65, 85], [0, 0.9], { extrapolateRight: 'clamp' })}
            style={{ filter: `drop-shadow(0 0 12px ${COLD_BLUE_GLOW})` }}
          />

          {/* Trough ripple rings */}
          {frame >= 90 && RING_OFFSETS.map((offset, ri) => {
            const rf = (pulsePhase + offset) % 45;
            const rProgress = rf / 45;
            const rR = 10 + rProgress * 55;
            const rOpacity = interpolate(rProgress, [0, 0.1, 0.7, 1], [0, 0.4, 0.35, 0]);
            return (
              <circle
                key={ri}
                cx={TROUGH_X} cy={troughY}
                r={rR}
                fill="none"
                stroke={COLD_BLUE}
                strokeWidth={1.5}
                opacity={rOpacity}
              />
            );
          })}

          {/* AM label — spring rise-up, GOLD */}
          <g transform={`translate(0, ${amSpringY})`} opacity={amOpacity * waveDim}>
            <text x={PEAK_X} y={PEAK_Y - 55} textAnchor="middle" fill={GOLD} fontSize={36} fontFamily={DM_SANS} fontWeight="500">
              AM
            </text>
            {/* Sun icon (6-point star) */}
            {[0, 60, 120, 180, 240, 300].map((a, si) => {
              const rad = (a * Math.PI) / 180;
              const sx = PEAK_X + 36 * Math.cos(rad);
              const sy = PEAK_Y - 100 + 36 * Math.sin(rad);
              return <circle key={si} cx={sx} cy={sy} r={2} fill={GOLD} opacity={0.6} />;
            })}
            <line x1={PEAK_X} y1={PEAK_Y - 38} x2={PEAK_X} y2={PEAK_Y - 10} stroke={GOLD} strokeWidth={1.5} opacity={0.6} />
          </g>

          {/* PM label — spring slam-down, COLD_BLUE */}
          <g transform={`translate(0, ${pmSpringY})`} opacity={pmOpacity * waveDim}>
            <line x1={TROUGH_X} y1={troughY + 14} x2={TROUGH_X} y2={troughY + 36} stroke={COLD_BLUE} strokeWidth={1.5} opacity={0.7} />
            <text x={TROUGH_X} y={troughY + 76} textAnchor="middle" fill={COLD_BLUE} fontSize={36} fontFamily={DM_SANS} fontWeight="500">
              PM
            </text>
            <text x={TROUGH_X} y={troughY + 118} textAnchor="middle" fill={WHITE_DIM} fontSize={26} fontFamily={DM_SANS}>
              dopamine lowest
            </text>
          </g>
        </g>
      </svg>
    </AbsoluteFill>
  );
};
