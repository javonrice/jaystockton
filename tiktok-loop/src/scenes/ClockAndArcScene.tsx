import React from 'react';
import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from 'remotion';
import { INDIGO, INDIGO_GLOW, WHITE, WHITE_DIM, WHITE_FAINT } from '../theme';
import { DM_SANS } from '../fonts';

const CX = 540;
const CY = 800;
const R = 220;
const ARC_R = 265;

const toRad = (deg: number) => (deg * Math.PI) / 180;
const hx = (r: number, deg: number) => CX + r * Math.sin(toRad(deg));
const hy = (r: number, deg: number) => CY - r * Math.cos(toRad(deg));

// Pre-calculated arc: from 230° to 370° (10° = same as 10°), spanning 140° clockwise
// The arc frames the 10 PM position (300°)
const ARC_START_DEG = 230;
const ARC_END_DEG = 370; // equivalent to 10° on the clock
const ARC_LEN = ARC_R * (140 * Math.PI) / 180; // ≈ 648

const arcPath = (): string => {
  const sx = hx(ARC_R, ARC_START_DEG);
  const sy = hy(ARC_R, ARC_START_DEG);
  const ex = hx(ARC_R, ARC_END_DEG);
  const ey = hy(ARC_R, ARC_END_DEG);
  return `M ${sx},${sy} A ${ARC_R},${ARC_R} 0 0 1 ${ex},${ey}`;
};

const ClockFace: React.FC<{ glow: number }> = ({ glow }) => {
  const ticks = Array.from({ length: 12 }, (_, i) => i);
  return (
    <g>
      {/* Face */}
      <circle cx={CX} cy={CY} r={R} fill="none" stroke={WHITE_FAINT} strokeWidth={2} />
      {/* Tick marks */}
      {ticks.map((i) => {
        const deg = i * 30;
        const inner = R - 14;
        const outer = R - 2;
        return (
          <line
            key={i}
            x1={hx(inner, deg)} y1={hy(inner, deg)}
            x2={hx(outer, deg)} y2={hy(outer, deg)}
            stroke={i === 0 || i === 3 || i === 6 || i === 9 ? WHITE_DIM : WHITE_FAINT}
            strokeWidth={i === 0 ? 3 : 1.5}
          />
        );
      })}
      {/* Glow ring at night */}
      {glow > 0 && (
        <circle
          cx={CX} cy={CY} r={R + 6}
          fill="none"
          stroke={INDIGO}
          strokeWidth={3}
          opacity={glow * 0.6}
          style={{ filter: `blur(4px)` }}
        />
      )}
    </g>
  );
};

const ClockHands: React.FC<{ hourAngle: number; glow: number }> = ({ hourAngle, glow }) => {
  const handColor = glow > 0 ? `rgba(${108 + glow * 40}, ${99 + glow * 60}, 255, 1)` : WHITE;
  const shadowFilter = glow > 0 ? `drop-shadow(0 0 ${8 * glow}px ${INDIGO})` : 'none';

  const hLen = 130;
  const mLen = 175;
  const minuteAngle = 0; // always 12 o'clock for simplicity

  return (
    <g style={{ filter: shadowFilter }}>
      {/* Hour hand */}
      <line
        x1={CX} y1={CY}
        x2={hx(hLen, hourAngle)} y2={hy(hLen, hourAngle)}
        stroke={hourAngle > 300 && hourAngle < 700 ? (glow > 0 ? INDIGO : WHITE) : WHITE}
        strokeWidth={8}
        strokeLinecap="round"
      />
      {/* Minute hand */}
      <line
        x1={CX} y1={CY}
        x2={hx(mLen, minuteAngle)} y2={hy(mLen, minuteAngle)}
        stroke={handColor}
        strokeWidth={4}
        strokeLinecap="round"
      />
      {/* Center dot */}
      <circle cx={CX} cy={CY} r={8} fill={glow > 0 ? INDIGO : WHITE} />
    </g>
  );
};

const TimeLabel: React.FC<{ text: string; deg: number; opacity: number; color?: string }> = ({
  text, deg, opacity, color = WHITE,
}) => {
  const lx = hx(R + 52, deg);
  const ly = hy(R + 52, deg);
  return (
    <text
      x={lx} y={ly}
      textAnchor="middle"
      dominantBaseline="middle"
      fill={color}
      fontSize={28}
      fontFamily={DM_SANS}
      opacity={opacity}
      fontWeight="500"
    >
      {text}
    </text>
  );
};

export const ClockAndArcScene: React.FC = () => {
  const frame = useCurrentFrame();
  const DURATION = 390;
  const FADE = 15;

  const sceneOpacity = interpolate(
    frame,
    [0, FADE, DURATION - FADE, DURATION],
    [0, 1, 1, 0],
    { extrapolateRight: 'clamp' },
  );

  // Clock hands: absolute angles (can exceed 360 for clockwise rotation tracking)
  // Morning: 210°, Afternoon: 420° (= 60°), Night: 660° (= 300°)
  const MORNING = 210;
  const AFTERNOON = 420;
  const NIGHT = 660;

  const hourAngle = (() => {
    if (frame < 75) return MORNING;
    if (frame < 90) return interpolate(frame, [75, 90], [MORNING, AFTERNOON], {
      easing: Easing.bezier(0.34, 1.56, 0.64, 1),
      extrapolateRight: 'clamp',
    });
    if (frame < 155) return AFTERNOON;
    if (frame < 170) return interpolate(frame, [155, 170], [AFTERNOON, NIGHT], {
      easing: Easing.bezier(0.34, 1.56, 0.64, 1),
      extrapolateRight: 'clamp',
    });
    return NIGHT;
  })();

  const glow = interpolate(frame, [170, 200], [0, 1], { extrapolateRight: 'clamp' });

  // Labels
  const morningOpacity = interpolate(frame, [15, 30, 75, 88], [0, 1, 1, 0], { extrapolateRight: 'clamp' });
  const afternoonOpacity = interpolate(frame, [88, 100, 152, 165], [0, 1, 1, 0], { extrapolateRight: 'clamp' });
  const nightOpacity = interpolate(frame, [168, 185, 280, 300], [0, 1, 1, 0], { extrapolateRight: 'clamp' });

  // Arc drawing: starts frame 230, draws over 70 frames
  const arcProgress = interpolate(frame, [230, 300], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.bezier(0.22, 1, 0.36, 1),
  });
  const arcOffset = ARC_LEN * (1 - arcProgress);
  const arcOpacity = interpolate(frame, [230, 245, 360, 390], [0, 1, 1, 0], {
    extrapolateRight: 'clamp',
  });

  // Clock fades when arc is done
  const clockFade = interpolate(frame, [240, 290], [1, 0], { extrapolateRight: 'clamp' });

  return (
    <AbsoluteFill style={{ opacity: sceneOpacity }}>
      <svg width={1080} height={1920} style={{ position: 'absolute', inset: 0 }}>
        <defs>
          <filter id="glow-filter">
            <feGaussianBlur stdDeviation="6" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {/* Clock */}
        <g opacity={clockFade}>
          <ClockFace glow={glow} />
          <ClockHands hourAngle={hourAngle % 360} glow={glow} />
          <TimeLabel text="7 AM" deg={210} opacity={morningOpacity} />
          <TimeLabel text="2 PM" deg={60} opacity={afternoonOpacity} />
          <TimeLabel text="10 PM" deg={300} opacity={nightOpacity} color={glow > 0.5 ? INDIGO : WHITE} />
        </g>

        {/* Purple arc */}
        <path
          d={arcPath()}
          fill="none"
          stroke={INDIGO}
          strokeWidth={6}
          strokeLinecap="round"
          strokeDasharray={ARC_LEN}
          strokeDashoffset={arcOffset}
          opacity={arcOpacity}
          style={{ filter: `drop-shadow(0 0 8px ${INDIGO_GLOW})` }}
        />
      </svg>
    </AbsoluteFill>
  );
};
