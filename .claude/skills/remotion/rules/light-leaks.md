---
name: light-leaks
description: Light leak overlay effects using @remotion/light-leaks
metadata:
  tags: light-leaks, transitions, effects, webgl
---

# Using Light Leaks in Remotion

The `<LightLeak>` component from `@remotion/light-leaks` renders a WebGL-based light leak effect (requires Remotion 4.0.415+).

## Prerequisites

```bash
npx remotion add @remotion/light-leaks # If project uses npm
bunx remotion add @remotion/light-leaks # If project uses bun
yarn remotion add @remotion/light-leaks # If project uses yarn
pnpm exec remotion add @remotion/light-leaks # If project uses pnpm
```

## Behavior

The component reveals during the first half of its duration and retracts during the second half.

## Props

- **durationInFrames** — defaults to parent duration; controls reveal and retract timing
- **seed** — generates different leak patterns (default: 0)
- **hueShift** — adjusts color in degrees 0–360 (default is yellow-orange; 120=green, 240=blue)

## As a Transition Overlay

The primary use case is within `<TransitionSeries.Overlay>` to create transitions between scenes:

```tsx
import { TransitionSeries } from "@remotion/transitions";
import { LightLeak } from "@remotion/light-leaks";

<TransitionSeries>
  <TransitionSeries.Sequence durationInFrames={60}>
    <SceneA />
  </TransitionSeries.Sequence>
  <TransitionSeries.Overlay durationInFrames={30}>
    <LightLeak seed={1} hueShift={0} />
  </TransitionSeries.Overlay>
  <TransitionSeries.Sequence durationInFrames={60}>
    <SceneB />
  </TransitionSeries.Sequence>
</TransitionSeries>
```

## As a Standalone Overlay

Use as a decorative overlay with `<AbsoluteFill>`:

```tsx
import { AbsoluteFill } from "remotion";
import { LightLeak } from "@remotion/light-leaks";

<AbsoluteFill>
  <MyContent />
  <AbsoluteFill>
    <LightLeak seed={2} hueShift={120} />
  </AbsoluteFill>
</AbsoluteFill>
```
