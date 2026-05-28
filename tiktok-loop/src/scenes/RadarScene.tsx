import React from 'react';
import { AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig } from 'remotion';
import { RED_PURPLE, RED_PURPLE_GLOW, WHITE_DIM } from '../theme';
import { TROUGH_X, TROUGH_Y, WAVE_PATH } from '../waveGeometry';
import { DM_SANS } from '../fonts';

const LINES = [
  { angle: -80 }, { angle: -55 }, { angle: -30, bright: true },
  { angle: -5  }, { angle: 20  }, { angle: 45  },
  { angle: 70  }, { angle: 100 },
];

const LINE_LEN = 320;
const SCAN_TEXT = 'scanning for the fastest option';

export const RadarScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const DURATION = 160;
  const FADE = 15;
  const SHOOT_START = 20;

  const sceneOpacity = interpolate(
    frame,
    [0, FADE, DURATION - FADE, DURATION],
    [0, 1, 1, 0],
    { extrapolateRight: 'clamp' },
  );

  const bgWaveOpacity = interpolate(frame, [0, FADE], [0, 0.18], { extrapolateRight: 'clamp' });

  // Staggered spring per line
  const lineLen = LINES.map((_, i) =>
    spring({
      frame: Math.max(0, frame - SHOOT_START - i * 3),
      fps,
      config: { damping: 18, stiffness: 180 },
      to: LINE_LEN,
      durationInFrames: 35,
    })
  );

  // Rotating sweep (one revolution per 60 frames)
  const sweepAngle = ((frame % 60) / 60) * 360;
  const sweepRad = (sweepAngle * Math.PI) / 180;
  const sweepEndRad = ((sweepAngle + 30) * Math.PI) / 180;
  const sweepSx = TROUGH_X + LINE_LEN * Math.cos(sweepRad);
  const sweepSy = TROUGH_Y + LINE_LEN * Math.sin(sweepRad);
  const sweepEx = TROUGH_X + LINE_LEN * Math.cos(sweepEndRad);
  const sweepEy = TROUGH_Y + LINE_LEN * Math.sin(sweepEndRad);
  const sweepOpacity = interpolate(frame, [SHOOT_START + 20, SHOOT_START + 35], [0, 0.5], { extrapolateRight: 'clamp' });

  // Flicker on bright line
  const scanFlicker = 0.55 + 0.45 * Math.sin((frame / 8) * Math.PI);

  // Typewriter text
  const typeProgress = interpolate(frame, [60, 95], [0, 1], { extrapolateRight: 'clamp' });
  const visibleChars = Math.floor(typeProgress * SCAN_TEXT.length);
  const displayText = SCAN_TEXT.slice(0, visibleChars);
  const cursor = frame >= 60 && frame < 130 && frame % 16 < 8 ? '|' : '';

  // Origin dot
  const dotOpacity = interpolate(frame, [0, FADE], [0, 1], { extrapolateRight: 'clamp' });

  return (
    <AbsoluteFill style={{ opacity: sceneOpacity }}>
      <svg width={1080} height={1920} style={{ position: 'absolute', inset: 0 }}>
        {/* Dim wave ghost in background with perspective feel */}
        <g opacity={bgWaveOpacity} transform={`translate(0, 40) scale(1, 0.94)`}>
          <path
            d={WAVE_PATH}
            fill="none"
            stroke={RED_PURPLE}
            strokeWidth={2}
            style={{ filter: `blur(1px)` }}
          />
        </g>

        {/* Origin dot */}
        <circle
          cx={TROUGH_X} cy={TROUGH_Y} r={10}
          fill={RED_PURPLE}
          opacity={dotOpacity}
          style={{ filter: `drop-shadow(0 0 8px ${RED_PURPLE_GLOW})` }}
        />

        {/* Radar lines with staggered spring */}
        {LINES.map(({ angle, bright }, i) => {
          const rad = (angle * Math.PI) / 180;
          const len = lineLen[i];
          const ex = TROUGH_X + len * Math.cos(rad);
          const ey = TROUGH_Y + len * Math.sin(rad);
          const opacity = bright ? scanFlicker : 0.28;

          return (
            <g key={i}>
              <line
                x1={TROUGH_X} y1={TROUGH_Y}
                x2={ex} y2={ey}
                stroke={bright ? RED_PURPLE : `rgba(192,63,192,0.6)`}
                strokeWidth={bright ? 3 : 1.5}
                opacity={opacity}
                style={bright ? { filter: `drop-shadow(0 0 8px ${RED_PURPLE_GLOW})` } : undefined}
              />
              {bright && len > LINE_LEN * 0.5 && (
                <circle
                  cx={ex} cy={ey} r={5}
                  fill={RED_PURPLE}
                  opacity={scanFlicker * 0.9}
                  style={{ filter: `drop-shadow(0 0 6px ${RED_PURPLE_GLOW})` }}
                />
              )}
            </g>
          );
        })}

        {/* Rotating sweep wedge */}
        <path
          d={`M ${TROUGH_X},${TROUGH_Y} L ${sweepSx},${sweepSy} A ${LINE_LEN},${LINE_LEN} 0 0 1 ${sweepEx},${sweepEy} Z`}
          fill={RED_PURPLE}
          opacity={sweepOpacity * 0.18}
        />
        <line
          x1={TROUGH_X} y1={TROUGH_Y}
          x2={sweepSx} y2={sweepSy}
          stroke={RED_PURPLE}
          strokeWidth={2}
          opacity={sweepOpacity * 0.7}
        />

        {/* Typewriter label */}
        <text
          x={540} y={1200}
          textAnchor="middle"
          fill={WHITE_DIM}
          fontSize={34}
          fontFamily={DM_SANS}
        >
          {displayText}{cursor}
        </text>
      </svg>
    </AbsoluteFill>
  );
};
