---
name: text-animations
description: Typography and text animation patterns in Remotion
metadata:
  tags: typography, text, typewriter, highlighter, animation
---

# Text Animations in Remotion

## Typewriter Effect

Reduce the string character by character to create a typewriter effect using `useCurrentFrame()`.

**Always use string slicing. Never use per-character opacity.**

```tsx
import { useCurrentFrame } from "remotion";

export const Typewriter = ({ text }: { text: string }) => {
  const frame = useCurrentFrame();
  const charsPerFrame = 0.5; // Adjust speed
  const visibleChars = Math.floor(frame * charsPerFrame);
  const displayText = text.slice(0, visibleChars);

  return (
    <div style={{ fontFamily: "monospace", fontSize: 48 }}>
      {displayText}
      <span style={{ opacity: Math.floor(frame / 15) % 2 === 0 ? 1 : 0 }}>|</span>
    </div>
  );
};
```

## Word Highlighting

Animate highlighted text like a highlighter pen effect:

```tsx
import { useCurrentFrame, interpolate } from "remotion";

export const HighlightedText = ({
  text,
  highlightStart,
  highlightDuration,
}: {
  text: string;
  highlightStart: number;
  highlightDuration: number;
}) => {
  const frame = useCurrentFrame();

  const highlightWidth = interpolate(
    frame,
    [highlightStart, highlightStart + highlightDuration],
    [0, 100],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  return (
    <div style={{ position: "relative", display: "inline-block" }}>
      <div
        style={{
          position: "absolute",
          bottom: 0,
          left: 0,
          width: `${highlightWidth}%`,
          height: "40%",
          background: "rgba(255, 255, 0, 0.6)",
          zIndex: 0,
        }}
      />
      <span style={{ position: "relative", zIndex: 1 }}>{text}</span>
    </div>
  );
};
```

## Word-by-Word Reveal

```tsx
import { useCurrentFrame, useVideoConfig } from "remotion";

export const WordReveal = ({ text }: { text: string }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const words = text.split(" ");
  const wordsPerSecond = 3;
  const visibleWords = Math.floor((frame / fps) * wordsPerSecond);

  return (
    <div>
      {words.map((word, i) => (
        <span
          key={i}
          style={{
            opacity: i < visibleWords ? 1 : 0,
            marginRight: "0.3em",
          }}
        >
          {word}
        </span>
      ))}
    </div>
  );
};
```
