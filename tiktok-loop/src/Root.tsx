import React from 'react';
import { Composition } from 'remotion';
import { LoopVideo } from './Composition';
import { DURATION, FPS, H, W } from './theme';

export const RemotionRoot: React.FC = () => (
  <Composition
    id="LoopVideo"
    component={LoopVideo}
    durationInFrames={DURATION}
    fps={FPS}
    width={W}
    height={H}
  />
);
