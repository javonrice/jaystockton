---
name: local-fonts
description: Loading local font files in Remotion using @remotion/fonts
metadata:
  tags: fonts, local, typography, custom
---

# Local Font Files with @remotion/fonts

## Prerequisites

```bash
npx remotion add @remotion/fonts # If project uses npm
bunx remotion add @remotion/fonts # If project uses bun
yarn remotion add @remotion/fonts # If project uses yarn
pnpm exec remotion add @remotion/fonts # If project uses pnpm
```

## Basic Usage

Place font files in the `public/` folder, then use `loadFont()` to register them:

```tsx
import { loadFont } from "@remotion/fonts";
import { staticFile } from "remotion";

const { fontFamily } = await loadFont({
  family: "MyFont",
  url: staticFile("fonts/MyFont-Regular.woff2"),
});

export const MyComposition = () => {
  return <div style={{ fontFamily }}>Hello World</div>;
};
```

## Multiple Font Weights

Load each weight separately with the same family name, using `Promise.all()` for efficiency:

```tsx
import { loadFont } from "@remotion/fonts";
import { staticFile } from "remotion";

await Promise.all([
  loadFont({
    family: "MyFont",
    url: staticFile("fonts/MyFont-Regular.woff2"),
    weight: "400",
  }),
  loadFont({
    family: "MyFont",
    url: staticFile("fonts/MyFont-Bold.woff2"),
    weight: "700",
  }),
]);
```

## Configuration Options

- **family** (required): CSS font family name
- **url** (required): Path using `staticFile()`
- **format** (optional): Font format, auto-detected from file extension
- **weight** (optional): Font weight value
- **style** (optional): `"normal"` or `"italic"`
- **display** (optional): Controls `font-display` behavior
