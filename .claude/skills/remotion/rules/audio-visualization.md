---
name: audio-visualization
description: Visualizing audio in Remotion with spectrum bars, waveforms, and bass-reactive effects.
metadata:
  tags: audio, visualization, spectrum, waveform, bass
---

# Audio Visualization in Remotion

## Prerequisites

```bash
npx remotion add @remotion/media-utils
```

## Spectrum Analysis

Use `visualizeAudio()` to generate frequency data for bar chart displays.  
`numberOfSamples` must be a power of 2 (32, 64, 128, 256, 512, 1024).  
Returns normalized values between 0 and 1.

```tsx
import { visualizeAudio } from "@remotion/media-utils";
import { useCurrentFrame, useVideoConfig, Audio } from "remotion";
import { useRef } from "react";

export const AudioBars = ({ src }: { src: string }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const audioRef = useRef<HTMLAudioElement>(null);

  const visualization = visualizeAudio({
    fps,
    frame,
    audioData: audioRef.current,
    numberOfSamples: 64,
  });

  return (
    <>
      <Audio src={src} ref={audioRef} />
      <div style={{ display: "flex", gap: 4 }}>
        {visualization.map((v, i) => (
          <div
            key={i}
            style={{ width: 10, height: v * 200, background: "white" }}
          />
        ))}
      </div>
    </>
  );
};
```

## Waveform Display

Use `visualizeAudioWaveform()` paired with `createSmoothSvgPath()` for oscilloscope-style visuals.

## Volume Data

Use `getWaveformPortion()` for simplified amplitude measurements when frequency spectrum analysis isn't needed.

## Critical Implementation Notes

When sharing `audioData` across child components, pass the `frame` value from the parent component rather than calling `useCurrentFrame()` independently in each child. This prevents discontinuous visualizations when children render within `<Sequence>` elements with timing offsets.

## Bass-Reactive Effects

Isolate low-frequency values from the frequency array to drive animation parameters like scale and opacity. Apply logarithmic scaling to raw frequency data since lower frequencies naturally dominate the output, improving visual balance.
