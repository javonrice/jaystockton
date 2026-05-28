import React from 'react';
import { AbsoluteFill, interpolate, interpolateColors, spring, useCurrentFrame, useVideoConfig } from 'remotion';
import { COLD_BLUE, COLD_BLUE_GLOW, GOLD, GOLD_GLOW, INDIGO, INDIGO_GLOW, WHITE, WHITE_DIM, WHITE_FAINT } from '../theme';
import { DM_SANS } from '../fonts';

const CX = 540;
const CY = 800;
const R = 220;
const ARC_R = 265;

const toRad = (deg: number) => (deg * Math.PI) / 180;
const hx = (r: number, deg: number) => CX + r * Math.sin(toRad(deg));
const hy = (r: number, deg: number) => CY - r * Math.cos(toRad(deg));

const ARC_START_DEG = 230;
const ARC_END_DEG = 370;
const ARC_LEN = ARC_R * (140 * Math.PI) / 180;

const arcPath = (): string => {
  const sx = hx(ARC_R, ARC_START_DEG);
  const sy = hy(ARC_R, ARC_START_DEG);
  const ex = hx(ARC_R, ARC_END_DEG);
  const ey = hy(ARC_R, ARC_END_DEG);
  return `M ${sx},${sy} A ${ARC_R},${ARC_R} 0 0 1 ${ex},${ey}`;
};

const ClockFace: React.FC<{ glow: number }> = ({ glow }) => {
  const ticks = Array.from({ length: 12 }, (_, i) => i);
  // Tick marks breathe slightly
  const frame = useCurrentFrame();
  const tickBreath = 0.3 + 0.15 * Math.sin((frame / 45) * Math.PI);
  const ringColor = interpolateColors(glow, [0, 1], [INDIGO, COLD_BLUE]);

  return (
    <g>
      <circle cx={CX} cy={CY} r={R} fill="none" stroke={WHITE_FAINT} strokeWidth={2} />
      {ticks.map((i) => {
        const deg = i * 30;
        const isMorning = i === 7; // ~7 AM position
        const inner = R - 14;
        const outer = R - 2;
        return (
          <line
            key={i}
            x1={hx(inner, deg)} y1={hy(inner, deg)}
            x2={hx(outer, deg)} y2={hy(outer, deg)}
            stroke={isMorning ? GOLD : (i === 0 || i === 3 || i === 6 || i === 9 ? WHITE_DIM : WHITE_FAINT)}
            strokeWidth={i === 0 ? 3 : 1.5}
            opacity={i === 0 || i === 3 || i === 6 || i === 9 ? 1 : tickBreath}
            style={isMorning ? { filter: `drop-shadow(0 0 4px ${GOLD_GLOW})` } : undefined}
          />
        );
      })}
      {glow > 0 && (
        <circle
          cx={CX} cy={CY} r={R + 6}
          fill="none"
          stroke={ringColor}
          strokeWidth={3}
          opacity={glow * 0.6}
          style={{ filter: `blur(4px)` }}
        />
      )}
    </g>
  );
};

const ClockHands: React.FC<{ hourAngle: number; glow: number }> = ({ hourAngle, glow }) => {
  const handColor = interpolateColors(glow, [0, 1], [WHITE, COLD_BLUE]);
  const shadowFilter = glow > 0 ? `drop-shadow(0 0 ${8 * glow}px ${COLD_BLUE})` : 'none';
  const hLen = 130;
  const mLen = 175;

  return (
    <g style={{ filter: shadowFilter }}>
      <line
        x1={CX} y1={CY}
        x2={hx(hLen, hourAngle)} y2={hy(hLen, hourAngle)}
        stroke={handColor}
        strokeWidth={8}
        strokeLinecap="round"
      />
      <line
        x1={CX} y1={CY}
        x2={hx(mLen, 0)} y2={hy(mLen, 0)}
        stroke={handColor}
        strokeWidth={4}
        strokeLinecap="round"
      />
      <circle cx={CX} cy={CY} r={8} fill={glow > 0.3 ? COLD_BLUE : WHITE} />
    </g>
  );
};

export const ClockAndArcScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const DURATION = 390;
  const FADE = 15;

  const sceneOpacity = interpolate(
    frame,
    [0, FADE, DURATION - FADE, DURATION],
    [0, 1, 1, 0],
    { extrapolateRight: 'clamp' },
  );

  const MORNING = 210;
  const AFTERNOON = 420;
  const NIGHT = 660;

  // Spring-physics hand jumps
  const hourAngle = (() => {
    if (frame < 75) return MORNING;
    if (frame < 155) {
      const s = spring({ frame: frame - 75, fps, config: { damping: 9, stiffness: 220 }, from: MORNING, to: AFTERNOON });
      return s;
    }
    const s = spring({ frame: frame - 155, fps, config: { damping: 9, stiffness: 220 }, from: AFTERNOON, to: NIGHT });
    return s;
  })();

  const glow = interpolate(frame, [170, 200], [0, 1], { extrapolateRight: 'clamp' });

  // Labels with spring slide-in
  const morningOpacity = interpolate(frame, [15, 30, 75, 88], [0, 1, 1, 0], { extrapolateRight: 'clamp' });
  const afternoonOpacity = interpolate(frame, [88, 100, 152, 165], [0, 1, 1, 0], { extrapolateRight: 'clamp' });
  const nightOpacity = interpolate(frame, [168, 185, 280, 300], [0, 1, 1, 0], { extrapolateRight: 'clamp' });

  const mornSlide = spring({ frame: Math.max(0, frame - 15), fps, config: { damping: 14, stiffness: 160 }, from: 30, to: 0 });
  const aftSlide  = spring({ frame: Math.max(0, frame - 88), fps, config: { damping: 14, stiffness: 160 }, from: 30, to: 0 });
  const nightSlide = spring({ frame: Math.max(0, frame - 168), fps, config: { damping: 14, stiffness: 160 }, from: 30, to: 0 });

  // Arc
  const arcProgress = interpolate(frame, [230, 300], [0, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
  });
  const arcOffset = ARC_LEN * (1 - arcProgress);
  const arcOpacity = interpolate(frame, [230, 245, 360, 390], [0, 1, 1, 0], { extrapolateRight: 'clamp' });

  // Arc trail particle position along arc at t = arcProgress
  const arcTrailAngle = ARC_START_DEG + (ARC_END_DEG - ARC_START_DEG) * arcProgress;
  const arcTrailX = hx(ARC_R, arcTrailAngle);
  const arcTrailY = hy(ARC_R, arcTrailAngle);

  // Arc glow pulse after fully drawn
  const arcGlowPulse = arcProgress >= 1 ? 0.6 + 0.4 * Math.sin(((frame - 300) / 30) * Math.PI) : 1;

  const clockFade = interpolate(frame, [240, 290], [1, 0], { extrapolateRight: 'clamp' });

  return (
    <AbsoluteFill style={{ opacity: sceneOpacity }}>
      {/* Subtle depth tilt on SVG */}
      <div style={{ position: 'absolute', inset: 0, perspective: '1200px' }}>
        <svg
          width={1080} height={1920}
          style={{ position: 'absolute', inset: 0, transform: 'rotateX(2deg)', transformOrigin: 'center center' }}
        >
          <defs>
            <filter id="glow-filter">
              <feGaussianBlur stdDeviation="6" result="blur" />
              <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
            </filter>
          </defs>

          <g opacity={clockFade}>
            <ClockFace glow={glow} />
            <ClockHands hourAngle={hourAngle % 360} glow={glow} />

            {/* 7 AM label — GOLD, slide in */}
            <text
              x={hx(R + 52, 210) + mornSlide} y={hy(R + 52, 210)}
              textAnchor="middle" dominantBaseline="middle"
              fill={GOLD} fontSize={28} fontFamily={DM_SANS} fontWeight="500"
              opacity={morningOpacity}
              style={{ filter: `drop-shadow(0 0 6px ${GOLD_GLOW})` }}
            >
              7 AM
            </text>

            {/* 2 PM label — WHITE_DIM, slide in */}
            <text
              x={hx(R + 52, 60) + aftSlide} y={hy(R + 52, 60)}
              textAnchor="middle" dominantBaseline="middle"
              fill={WHITE_DIM} fontSize={28} fontFamily={DM_SANS} fontWeight="500"
              opacity={afternoonOpacity}
            >
              2 PM
            </text>

            {/* 10 PM label — COLD_BLUE when glowing, slide in */}
            <text
              x={hx(R + 52, 300) + nightSlide} y={hy(R + 52, 300)}
              textAnchor="middle" dominantBaseline="middle"
              fill={glow > 0.5 ? COLD_BLUE : WHITE} fontSize={28} fontFamily={DM_SANS} fontWeight="500"
              opacity={nightOpacity}
              style={glow > 0.5 ? { filter: `drop-shadow(0 0 6px ${COLD_BLUE_GLOW})` } : undefined}
            >
              10 PM
            </text>
          </g>

          {/* Arc in COLD_BLUE (night color) */}
          <path
            d={arcPath()}
            fill="none"
            stroke={COLD_BLUE}
            strokeWidth={6}
            strokeLinecap="round"
            strokeDasharray={ARC_LEN}
            strokeDashoffset={arcOffset}
            opacity={arcOpacity}
            style={{ filter: `drop-shadow(0 0 ${8 * arcGlowPulse}px ${COLD_BLUE_GLOW})` }}
          />

          {/* Arc trail particle */}
          {arcProgress > 0 && arcProgress < 1 && (
            <circle
              cx={arcTrailX} cy={arcTrailY} r={6}
              fill={COLD_BLUE}
              opacity={0.9}
              style={{ filter: `blur(3px) drop-shadow(0 0 8px ${COLD_BLUE})` }}
            />
          )}
        </svg>
      </div>
    </AbsoluteFill>
  );
};
