import React from 'react';
import { AbsoluteFill, Audio, Sequence, staticFile } from 'remotion';
import { BG } from './theme';
import { ClockAndArcScene } from './scenes/ClockAndArcScene';
import { DotScene } from './scenes/DotScene';
import { WaveScene } from './scenes/WaveScene';
import { RadarScene } from './scenes/RadarScene';
import { CountdownScene } from './scenes/CountdownScene';
import { WordsScene } from './scenes/WordsScene';
import { WindowScene } from './scenes/WindowScene';
import { CTAScene } from './scenes/CTAScene';
import { Subtitles } from './Subtitles';
import { AmbientBackground } from './components/AmbientBackground';
import { LightLeakOverlay } from './components/LightLeakOverlay';

// ──────────────────────────────────────────────────
//  Scene timing (global frames, 30 fps)
//  0    – 390  ClockAndArc
//  370  – 465  Dot
//  450  – 680  Wave
//  660  – 820  Radar
//  805  – 945  Countdown
//  930  – 1040 Words   (extended +15 for TIMING spring)
//  1015 – 1110 Window
//  1085 – 1230 CTA
// ──────────────────────────────────────────────────

export const LoopVideo: React.FC = () => (
  <AbsoluteFill style={{ backgroundColor: BG }}>
    {/* Voiceover */}
    <Audio src={staticFile('voiceover.mp3')} />

    {/* Global ambient background — reads global frame, runs full duration */}
    <AmbientBackground />

    {/* Scenes */}
    <Sequence from={0}    durationInFrames={390}><ClockAndArcScene /></Sequence>
    <Sequence from={370}  durationInFrames={95}> <DotScene /></Sequence>
    <Sequence from={450}  durationInFrames={230}><WaveScene /></Sequence>
    <Sequence from={660}  durationInFrames={160}><RadarScene /></Sequence>
    <Sequence from={805}  durationInFrames={140}><CountdownScene /></Sequence>
    <Sequence from={930}  durationInFrames={110}><WordsScene /></Sequence>
    <Sequence from={1015} durationInFrames={95}> <WindowScene /></Sequence>
    <Sequence from={1085} durationInFrames={145}><CTAScene /></Sequence>

    {/* Light leak flashes at scene boundaries */}
    <Sequence from={368}  durationInFrames={22}><LightLeakOverlay corner="top-right"  colorHint="gold"       /></Sequence>
    <Sequence from={448}  durationInFrames={20}><LightLeakOverlay corner="top-left"   colorHint="white"      /></Sequence>
    <Sequence from={658}  durationInFrames={20}><LightLeakOverlay corner="center"     colorHint="red-purple" /></Sequence>
    <Sequence from={803}  durationInFrames={20}><LightLeakOverlay corner="top-right"  colorHint="cold-blue"  /></Sequence>
    <Sequence from={928}  durationInFrames={16}><LightLeakOverlay corner="center"     colorHint="white"      /></Sequence>
    <Sequence from={1013} durationInFrames={16}><LightLeakOverlay corner="center"     colorHint="white"      /></Sequence>
    <Sequence from={1083} durationInFrames={20}><LightLeakOverlay corner="top-left"   colorHint="gold"       /></Sequence>

    {/* SFX at volume 0.4 to sit under voiceover */}
    <Sequence from={75}   durationInFrames={18}><Audio src={staticFile('whoosh.wav')} volume={0.4} /></Sequence>
    <Sequence from={155}  durationInFrames={18}><Audio src={staticFile('whoosh.wav')} volume={0.4} /></Sequence>
    <Sequence from={400}  durationInFrames={20}><Audio src={staticFile('ding.wav')}   volume={0.4} /></Sequence>
    <Sequence from={515}  durationInFrames={18}><Audio src={staticFile('whip.wav')}   volume={0.4} /></Sequence>
    <Sequence from={680}  durationInFrames={18}><Audio src={staticFile('whoosh.wav')} volume={0.4} /></Sequence>
    <Sequence from={820}  durationInFrames={18}><Audio src={staticFile('whip.wav')}   volume={0.4} /></Sequence>
    <Sequence from={952}  durationInFrames={18}><Audio src={staticFile('whip.wav')}   volume={0.4} /></Sequence>
    <Sequence from={978}  durationInFrames={20}><Audio src={staticFile('ding.wav')}   volume={0.4} /></Sequence>
    <Sequence from={1095} durationInFrames={20}><Audio src={staticFile('ding.wav')}   volume={0.4} /></Sequence>

    {/* Subtitles always on top */}
    <Subtitles />
  </AbsoluteFill>
);
