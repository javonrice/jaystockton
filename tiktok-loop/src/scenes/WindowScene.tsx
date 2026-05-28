import React from 'react';
import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from 'remotion';
import { COLD_BLUE, COLD_BLUE_GLOW, INDIGO, INDIGO_GLOW, WHITE } from '../theme';
import { SYNE } from '../fonts';
import { TROUGH_X, TROUGH_Y, WAVE_PATH } from '../waveGeometry';

const BOX = { x: 680, y: 890, w: 260, h: 160 };
const PERIMETER = 2 * (BOX.w + BOX.h);
// Corner thresholds along perimeter (clockwise from top-left)
const CORNERS = [0, BOX.w, BOX.w + BOX.h, 2 * BOX.w + BOX.h, PERIMETER];
const RING_OFFSETS = [0, 16, 32];

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

  const waveOpacity = interpolate(frame, [0, 20], [0, 0.55], { extrapolateRight: 'clamp' });

  const boxProgress = interpolate(frame, [22, 55], [0, 1], {
    extrapolateRight: 'clamp',
    easing: Easing.bezier(0.22, 1, 0.36, 1),
  });
  const boxDash = PERIMETER * boxProgress;

  // Perspective: box starts tilted, flattens as it materializes
  const perspRotX = interpolate(boxProgress, [0, 1], [8, 0]);

  // Interior fill breathes
  const fillOpacity = boxProgress >= 1 ? 0.04 + 0.04 * Math.sin((frame / 20) * Math.PI) : 0;

  // Corner flash dots — appear briefly when boxDash crosses each corner
  const cornerFlashes = CORNERS.slice(0, 4).map((threshold) => {
    const dist = boxDash - threshold;
    if (dist < 0 || dist > 25) return 0;
    return interpolate(dist, [0, 5, 20, 25], [0, 0.9, 0.9, 0]);
  });

  const cornerPositions = [
    { x: BOX.x,           y: BOX.y },
    { x: BOX.x + BOX.w,   y: BOX.y },
    { x: BOX.x + BOX.w,   y: BOX.y + BOX.h },
    { x: BOX.x,           y: BOX.y + BOX.h },
  ];

  const textOpacity = interpolate(frame, [58, 72], [0, 1], { extrapolateRight: 'clamp' });

  // Trough ripple rings
  const pulsePhase = Math.max(0, frame - 22);

  return (
    <AbsoluteFill style={{ opacity: sceneOpacity }}>
      <div style={{ position: 'absolute', inset: 0, perspective: '600px' }}>
        <svg
          width={1080} height={1920}
          style={{
            position: 'absolute', inset: 0,
            transform: `rotateX(${perspRotX * boxProgress < 0.99 ? perspRotX : 0}deg)`,
            transformOrigin: 'center 965px',
          }}
        >
          {/* Dimmed wave ghost — blurred into background */}
          <path
            d={WAVE_PATH}
            fill="none"
            stroke={INDIGO}
            strokeWidth={3}
            opacity={waveOpacity}
            style={{ filter: `blur(1.5px)` }}
          />

          {/* Trough dot */}
          <circle cx={TROUGH_X} cy={TROUGH_Y} r={8} fill={COLD_BLUE} opacity={waveOpacity} />

          {/* Trough ripple rings */}
          {RING_OFFSETS.map((offset, ri) => {
            const rf = (pulsePhase + offset) % 45;
            const rProgress = rf / 45;
            const rR = 8 + rProgress * 50;
            const rOpacity = waveOpacity * interpolate(rProgress, [0, 0.1, 0.7, 1], [0, 0.35, 0.3, 0]);
            return (
              <circle
                key={ri}
                cx={TROUGH_X} cy={TROUGH_Y}
                r={rR}
                fill="none"
                stroke={COLD_BLUE}
                strokeWidth={1.5}
                opacity={rOpacity}
              />
            );
          })}

          {/* Box with breathing interior fill */}
          <rect
            x={BOX.x} y={BOX.y}
            width={BOX.w} height={BOX.h}
            fill={`rgba(108, 99, 255, ${fillOpacity})`}
            stroke={INDIGO}
            strokeWidth={3}
            rx={6}
            strokeDasharray={PERIMETER}
            strokeDashoffset={PERIMETER - boxDash}
            style={{ filter: `drop-shadow(0 0 8px ${INDIGO_GLOW})` }}
          />

          {/* Corner flash dots */}
          {cornerPositions.map((pos, i) => (
            <circle
              key={i}
              cx={pos.x} cy={pos.y} r={6}
              fill={COLD_BLUE}
              opacity={cornerFlashes[i]}
              style={{ filter: `drop-shadow(0 0 4px ${COLD_BLUE_GLOW})` }}
            />
          ))}

          {/* YOUR WINDOW labels */}
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
            fill={COLD_BLUE}
            fontSize={26}
            fontFamily={SYNE}
            fontWeight="700"
            opacity={textOpacity}
            letterSpacing={2}
            style={{ filter: `drop-shadow(0 0 6px ${COLD_BLUE_GLOW})` }}
          >
            WINDOW
          </text>
        </svg>
      </div>
    </AbsoluteFill>
  );
};
