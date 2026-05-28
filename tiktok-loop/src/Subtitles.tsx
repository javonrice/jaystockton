import React from 'react';
import { AbsoluteFill, useCurrentFrame, useVideoConfig } from 'remotion';
import { captions } from './captions';
import { DM_SANS } from './fonts';
import { WHITE } from './theme';

export const Subtitles: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const currentMs = (frame / fps) * 1000;

  const active = captions.find(
    (c) => currentMs >= c.startMs && currentMs < c.endMs,
  );

  if (!active) return null;

  return (
    <AbsoluteFill
      style={{
        justifyContent: 'flex-end',
        alignItems: 'center',
        paddingBottom: 180,
        paddingLeft: 60,
        paddingRight: 60,
        pointerEvents: 'none',
      }}
    >
      <div
        style={{
          color: WHITE,
          fontFamily: DM_SANS,
          fontSize: 54,
          fontWeight: 500,
          textAlign: 'center',
          lineHeight: 1.3,
          textShadow: '0 2px 12px rgba(0,0,0,0.9), 0 0 40px rgba(0,0,0,0.7)',
          maxWidth: 960,
        }}
      >
        {active.text}
      </div>
    </AbsoluteFill>
  );
};
