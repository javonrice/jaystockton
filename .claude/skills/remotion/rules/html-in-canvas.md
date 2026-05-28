---
name: html-in-canvas
description: Rendering HTML into a canvas element for 2D or WebGL post-processing effects
metadata:
  tags: canvas, webgl, html, effects
---

# Using `<HtmlInCanvas>` in Remotion

Render children into a canvas element for post-processing with Canvas 2D API or WebGL.

## Requirements

The feature requires Chrome 149+ with the `chrome://flags/#canvas-draw-element` flag enabled.

## Important Constraints

Nesting multiple `<HtmlInCanvas>` components is not supported. The framework will throw an error:
> "effects cannot be nested together. Chrome will only display the outer effect."

## Setup for WebGL

Enable WebGL rendering via CLI:

```bash
npx remotion render --gl=angle
```

Or configure as default in `remotion.config.ts`:

```ts
Config.setChromiumOpenGlRenderer("angle");
```

## Basic Usage (Canvas 2D)

The `onPaint` callback executes when content updates, allowing custom Canvas 2D transformations:

```tsx
import { HtmlInCanvas } from "remotion";

export const MyComposition = () => {
  return (
    <HtmlInCanvas
      onPaint={({ ctx, width, height }) => {
        // Apply Canvas 2D effects here
        ctx.filter = "blur(4px)";
        ctx.drawImage(ctx.canvas, 0, 0);
      }}
    >
      <div style={{ background: "red", width: 100, height: 100 }} />
    </HtmlInCanvas>
  );
};
```

## WebGL Usage

Configure context and resources in `onInit`, returning a cleanup function. Upload DOM images in `onPaint` using `gl.texElementImage2D(...)`.

## Async `onPaint`

Async `onPaint` is supported — Remotion maintains frame timing via `delayRender()` until promises resolve, enabling multi-pass effects with `createImageBitmap`.
