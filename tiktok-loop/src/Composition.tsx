import React from 'react';
import { AbsoluteFill, Audio, Sequence, staticFile } from 'remotion';
import { BG, DURATION, FPS, H, W } from './theme';
import { ClockAndArcScene } from './scenes/ClockAndArcScene';
import { DotScene } from './scenes/DotScene';
import { WaveScene } from './scenes/WaveScene';
import { RadarScene } from './scenes/RadarScene';
import { CountdownScene } from './scenes/CountdownScene';
import { WordsScene } from './scenes/WordsScene';
import { WindowScene } from './scenes/WindowScene';
import { CTAScene } from './scenes/CTAScene';
import { Subtitles } from './Subtitles';

// ──────────────────────────────────────────────
//  Scene timing (global frames, 30 fps)
//  Scenes overlap by ~15 frames for crossfades.
// ──────────────────────────────────────────────
//  0   – 390  ClockAndArc
//  370 – 465  Dot            (+15 overlap with clock fade-out)
//  450 – 680  Wave           (+15 overlap with dot fade-out)
//  660 – 820  Radar          (+20 overlap with wave fade-out)
//  805 – 945  Countdown      (+15 overlap with radar fade-out)
//  930 – 1025 Words          (+15 overlap with countdown fade-out)
//  1015– 1110 Window         (+10 overlap with words fade-out)
//  1095– 1140 CTA            (+15 overlap with window fade-out)
// ──────────────────────────────────────────────

export const LoopVideo: React.FC = () => (
  <AbsoluteFill style={{ backgroundColor: BG }}>
    {/* Voiceover — place voiceover.mp3 in public/ */}
    <Audio src={staticFile('voiceover.mp3')} />

    <Sequence from={0}    durationInFrames={390}><ClockAndArcScene /></Sequence>
    <Sequence from={370}  durationInFrames={95}> <DotScene /></Sequence>
    <Sequence from={450}  durationInFrames={230}><WaveScene /></Sequence>
    <Sequence from={660}  durationInFrames={160}><RadarScene /></Sequence>
    <Sequence from={805}  durationInFrames={140}><CountdownScene /></Sequence>
    <Sequence from={930}  durationInFrames={95}> <WordsScene /></Sequence>
    <Sequence from={1015} durationInFrames={95}> <WindowScene /></Sequence>
    <Sequence from={1095} durationInFrames={45}> <CTAScene /></Sequence>

    {/* Subtitles always on top */}
    <Subtitles />
  </AbsoluteFill>
);
