import React from 'react';
import { AbsoluteFill, interpolateColors, useCurrentFrame } from 'remotion';
import { W, H } from '../theme';

const SEEDS = Array.from({ length: 40 }, (_, i) => {
  const s = (i * 2654435761) >>> 0;
  return {
    x: (s % W),
    y: ((s * 1234567) % H),
    freqX: 60 + (s % 40),
    freqY: 80 + ((s * 3) % 30),
    phaseX: (s % 628) / 100,
    phaseY: ((s * 7) % 628) / 100,
    opFreq: 50 + (s % 25),
    opPhase: (s % 314) / 100,
    r: 1 + ((s % 25) / 10),
  };
});

export const AmbientBackground: React.FC = () => {
  const frame = useCurrentFrame();

  const bgTint = interpolateColors(
    frame,
    [0, 130, 370, 450, 660, 805, 930, 1085, 1230],
    [
      '#0D0D0F',
      '#120E08',
      '#0D0D0F',
      '#08080F',
      '#09080E',
      '#0D080E',
      '#0D0D0F',
      '#0D0D0F',
      '#120E08',
    ],
  );

  const breathe = 1 + 0.003 * Math.sin((frame / 120) * Math.PI * 2);

  return (
    <AbsoluteFill style={{ pointerEvents: 'none' }}>
      {/* Layer A — breathing tinted gradient */}
      <AbsoluteFill
        style={{
          background: `radial-gradient(ellipse ${60 * breathe}% ${50 * breathe}% at 50% 50%, ${bgTint} 0%, #0D0D0F 100%)`,
        }}
      />

      {/* Layer B — particle field */}
      <AbsoluteFill>
        <svg width={W} height={H} style={{ position: 'absolute', top: 0, left: 0 }}>
          {SEEDS.map((p, i) => {
            const dx = Math.sin(frame / p.freqX + p.phaseX) * 12;
            const dy = Math.cos(frame / p.freqY + p.phaseY) * 18;
            const opacity = 0.05 + 0.15 * Math.abs(Math.sin(frame / p.opFreq + p.opPhase));
            return (
              <circle
                key={i}
                cx={p.x + dx}
                cy={p.y + dy}
                r={p.r}
                fill="#6C63FF"
                opacity={opacity}
              />
            );
          })}
        </svg>
      </AbsoluteFill>

      {/* Layer C — scanline texture */}
      <AbsoluteFill
        style={{
          background: 'repeating-linear-gradient(0deg, rgba(0,0,0,0.04) 0px, rgba(0,0,0,0.04) 1px, transparent 1px, transparent 2px)',
          pointerEvents: 'none',
        }}
      />
    </AbsoluteFill>
  );
};
