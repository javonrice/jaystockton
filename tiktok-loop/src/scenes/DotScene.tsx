import React from 'react';
import { AbsoluteFill, interpolate, interpolateColors, spring, useCurrentFrame, useVideoConfig } from 'remotion';
import { INDIGO, NEURAL_GREEN, WHITE } from '../theme';

const CX = 540;
const CY = 760;
const LINE_LEN = 120;
const NUM_LINES = 10;

// Pre-calculate random angles and stagger delays for the burst lines
const BURST_LINES = Array.from({ length: NUM_LINES }, (_, i) => ({
  angle: (i / NUM_LINES) * 360 + ((i * 37) % 30) - 15,
  delay: i * 2,
}));

// Concentric rings spawn at pulse peaks (every 40 frames from local frame 55)
const RING_OFFSETS = [0, 12, 24];

export const DotScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const DURATION = 95;
  const FADE = 15;

  const sceneOpacity = interpolate(
    frame,
    [0, FADE, DURATION - FADE, DURATION],
    [0, 1, 1, 0],
    { extrapolateRight: 'clamp' },
  );

  // Phase 1 (0–30): burst lines shoot out
  // Phase 2 (30–55): lines retract, central dot scales in
  // Phase 3 (55–95): dot breathes + concentric rings

  // Per-line length via staggered spring (shoot out)
  const lineProgress = BURST_LINES.map(({ delay }) =>
    spring({ frame: Math.max(0, frame - delay), fps, config: { damping: 18, stiffness: 160 }, from: 0, to: 1, durationInFrames: 20 })
  );

  // Lines retract after frame 30
  const retractProgress = interpolate(frame, [30, 48], [0, 1], {
    extrapolateRight: 'clamp',
    easing: (t) => t * t,
  });

  // Central dot: spring scale in at frame 30
  const dotScale = spring({
    frame: Math.max(0, frame - 30),
    fps,
    config: { damping: 14, stiffness: 240 },
    from: 0,
    to: 1,
  });

  const dotColor = interpolateColors(
    Math.min(frame - 30, 25),
    [0, 25],
    [NEURAL_GREEN, WHITE],
  );

  // Phase 3: pulse breathing
  const pulseT = Math.max(0, frame - 55);
  const pulseScale = 1 + 0.3 * Math.sin((pulseT / 40) * Math.PI * 2);
  const pulseOpacity = 0.7 + 0.3 * Math.sin((pulseT / 40) * Math.PI * 2);

  const finalScale = frame < 30 ? 0 : dotScale * (frame >= 55 ? pulseScale : 1);
  const finalOpacity = frame < 30 ? 0 : (frame >= 55 ? pulseOpacity : 1);

  return (
    <AbsoluteFill style={{ opacity: sceneOpacity }}>
      <svg width={1080} height={1920} style={{ position: 'absolute', inset: 0 }}>
        {/* Burst lines (Phase 1 + retract in Phase 2) */}
        {frame < 55 && BURST_LINES.map(({ angle, delay }, i) => {
          const rad = (angle * Math.PI) / 180;
          const rawLen = lineProgress[i] * LINE_LEN;
          const len = rawLen * (1 - retractProgress);
          const ex = CX + len * Math.cos(rad);
          const ey = CY + len * Math.sin(rad);
          const lineOpacity = (1 - retractProgress) * (frame >= delay ? 1 : 0);

          return (
            <g key={i} opacity={lineOpacity}>
              <line
                x1={CX} y1={CY}
                x2={ex} y2={ey}
                stroke={NEURAL_GREEN}
                strokeWidth={1.5}
                strokeLinecap="round"
              />
              {len > 10 && (
                <circle cx={ex} cy={ey} r={3} fill={NEURAL_GREEN} opacity={0.8} />
              )}
            </g>
          );
        })}

        {/* Central dot */}
        {frame >= 30 && (
          <circle
            cx={CX} cy={CY}
            r={12 * finalScale}
            fill={dotColor}
            opacity={finalOpacity}
            style={{
              filter: `drop-shadow(0 0 ${14 * finalScale}px ${frame >= 55 ? 'rgba(255,255,255,0.35)' : NEURAL_GREEN})`,
            }}
          />
        )}

        {/* Concentric ripple rings (Phase 3) */}
        {frame >= 55 && RING_OFFSETS.map((offset, ri) => {
          const ringFrame = (frame - 55 + offset) % 40;
          const ringProgress = ringFrame / 40;
          const ringR = 12 + ringProgress * 50;
          const ringOpacity = interpolate(ringProgress, [0, 0.1, 0.7, 1], [0, 0.4, 0.4, 0]);
          return (
            <circle
              key={ri}
              cx={CX} cy={CY}
              r={ringR}
              fill="none"
              stroke={INDIGO}
              strokeWidth={1.5}
              opacity={ringOpacity}
            />
          );
        })}
      </svg>
    </AbsoluteFill>
  );
};
