---
name: sequencing
description: Advanced sequencing patterns in Remotion - delay, trim, limit duration
metadata:
  tags: sequence, timing, series, delay, duration
---

# Sequencing Patterns in Remotion

## Basic Sequence

Use `<Sequence>` to delay when an element appears in the timeline:

```tsx
import { Sequence } from "remotion";

const { fps } = useVideoConfig();

<Sequence from={30} durationInFrames={60}>
  <MyComponent />
</Sequence>
```

Inside `<MyComponent>`, `useCurrentFrame()` starts at 0, not the global frame.

## Layout Control

By default, sequences wrap components in an absolute fill element. Use `layout="none"` for inline content:

```tsx
<Sequence from={30} layout="none">
  <span>Inline text</span>
</Sequence>
```

## Premounting

Always premount sequences using the `premountFor` prop to load components before playback:

```tsx
<Sequence from={60} premountFor={30}>
  <HeavyComponent />
</Sequence>
```

## Series Component

For sequential, non-overlapping elements, use `<Series>` with `<Series.Sequence>` children:

```tsx
import { Series } from "remotion";

<Series>
  <Series.Sequence durationInFrames={60}>
    <SceneA />
  </Series.Sequence>
  <Series.Sequence durationInFrames={60}>
    <SceneB />
  </Series.Sequence>
  <Series.Sequence durationInFrames={60}>
    <SceneC />
  </Series.Sequence>
</Series>
```

## Overlapping with Series

Create overlaps in `<Series>` using negative `offset` values:

```tsx
<Series>
  <Series.Sequence durationInFrames={60}>
    <SceneA />
  </Series.Sequence>
  <Series.Sequence durationInFrames={60} offset={-15}>
    {/* Starts 15 frames before SceneA ends */}
    <SceneB />
  </Series.Sequence>
</Series>
```

## Nesting Compositions

Embed compositions within other compositions by specifying `width` and `height`:

```tsx
<AbsoluteFill>
  <Sequence width={COMPOSITION_WIDTH} height={COMPOSITION_HEIGHT}>
    <CompositionComponent />
  </Sequence>
</AbsoluteFill>
```
