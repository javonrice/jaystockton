import React from 'react';
import { AbsoluteFill, Easing, interpolate, spring, useCurrentFrame, useVideoConfig } from 'remotion';
import { INDIGO, INDIGO_GLOW, RED_PURPLE, RED_PURPLE_GLOW, WHITE } from '../theme';
import { SYNE } from '../fonts';
import { LightLeakOverlay } from '../components/LightLeakOverlay';

export const WordsScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const DURATION = 110;
  const FADE = 12;

  const sceneOpacity = interpolate(
    frame,
    [0, FADE, DURATION - FADE, DURATION],
    [0, 1, 1, 0],
    { extrapolateRight: 'clamp' },
  );

  // WILLPOWER: spring slam-down entry
  const willSpringY = spring({ frame, fps, config: { damping: 8, stiffness: 200 }, from: -80, to: 0 });
  const willSpringS = spring({ frame, fps, config: { damping: 8, stiffness: 200 }, from: 1.15, to: 1 });
  const willVisible = frame >= 1 ? 1 : 0;

  // Strikethrough draws left-to-right (RED_PURPLE, violent/decisive)
  const strikeWidth = interpolate(frame, [22, 45], [0, 560], {
    extrapolateRight: 'clamp',
    easing: Easing.bezier(0.22, 1, 0.36, 1),
  });

  // WILLPOWER dims out after strikethrough completes
  const willOpacityBase = interpolate(frame, [45, 60], [0.55, 0.18], { extrapolateRight: 'clamp' });

  // TIMING: spring scale + rise-up with low damping = 2-3 bounces
  const tFrame = Math.max(0, frame - 48);
  const timingScale = spring({ frame: tFrame, fps, config: { damping: 6, stiffness: 300 }, from: 0, to: 1 });
  const timingY = spring({ frame: tFrame, fps, config: { damping: 6, stiffness: 300 }, from: 40, to: 0 });

  // Impact color flash: RED_PURPLE on first bounce frames, settles to INDIGO
  const impactFlash = interpolate(tFrame, [0, 3, 8], [0, 1, 0], { extrapolateRight: 'clamp' });
  const glowR = Math.floor(108 + impactFlash * 84);   // 108 → 192
  const glowG = Math.floor(99 - impactFlash * 36);    // 99 → 63
  const glowA1 = (0.45 + impactFlash * 0.4).toFixed(2);
  const glowA2 = (0.2 + impactFlash * 0.2).toFixed(2);
  const timingGlowPulse = 0.7 + 0.3 * Math.sin((frame / 18) * Math.PI);
  const timingGlowColor = `rgba(${glowR}, ${glowG}, 255, ${glowA1})`;

  return (
    <AbsoluteFill
      style={{
        opacity: sceneOpacity,
        alignItems: 'center',
        justifyContent: 'center',
        flexDirection: 'column',
        gap: 0,
      }}
    >
      {/* WILLPOWER + strikethrough */}
      <div
        style={{
          position: 'relative',
          display: 'inline-block',
          marginTop: -180,
          opacity: willVisible * willOpacityBase,
          transform: `translateY(${willSpringY}px) scale(${willSpringS})`,
          willChange: 'transform',
        }}
      >
        <div
          style={{
            fontFamily: SYNE,
            fontWeight: 700,
            fontSize: 108,
            color: WHITE,
            letterSpacing: -2,
            lineHeight: 1,
          }}
        >
          WILLPOWER
        </div>
        {/* RED_PURPLE strikethrough */}
        <div
          style={{
            position: 'absolute',
            top: '50%',
            left: '50%',
            transform: 'translate(-50%, -50%)',
            width: strikeWidth,
            height: 7,
            backgroundColor: RED_PURPLE,
            borderRadius: 4,
            boxShadow: `0 0 18px ${RED_PURPLE_GLOW}, 0 0 40px ${RED_PURPLE_GLOW}`,
          }}
        />
      </div>

      {/* TIMING — the emotional peak */}
      <div
        style={{
          fontFamily: SYNE,
          fontWeight: 700,
          fontSize: 130,
          color: INDIGO,
          letterSpacing: -2,
          lineHeight: 1,
          marginTop: 24,
          transform: `scale(${timingScale}) translateY(${timingY}px)`,
          opacity: frame >= 48 ? 1 : 0,
          textShadow: `0 0 ${40 * timingGlowPulse}px ${timingGlowColor}, 0 0 ${80 * timingGlowPulse}px rgba(108,99,255,${glowA2})`,
          willChange: 'transform',
        }}
      >
        TIMING
      </div>

      {/* Climax flash when TIMING lands */}
      {frame >= 48 && frame < 58 && (
        <LightLeakOverlay corner="center" colorHint="white" durationInFrames={10} />
      )}
    </AbsoluteFill>
  );
};
