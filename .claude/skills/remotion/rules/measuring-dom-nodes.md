---
name: measuring-dom-nodes
description: Measuring DOM element dimensions in Remotion accounting for scale transforms
metadata:
  tags: dom, measuring, dimensions, scale, layout
---

# Measuring DOM Nodes in Remotion

Remotion applies a scale transform to the video container, which impacts `getBoundingClientRect()` values. To obtain accurate measurements, use the `useCurrentScale()` hook.

## Usage

```tsx
import { useCurrentScale } from "remotion";
import { useRef } from "react";

export const MyComponent = () => {
  const ref = useRef<HTMLDivElement>(null);
  const scale = useCurrentScale();

  const measureElement = () => {
    if (!ref.current) return;

    const rect = ref.current.getBoundingClientRect();

    // Divide by scale to compensate for Remotion's transform
    const actualWidth = rect.width / scale;
    const actualHeight = rect.height / scale;

    console.log({ actualWidth, actualHeight });
  };

  return <div ref={ref}>Content</div>;
};
```

Dividing by the scale factor ensures dimensions reflect actual layout metrics rather than transformed (scaled) values. This is essential when working with Remotion videos where scale transforms would otherwise distort measurement readings.
