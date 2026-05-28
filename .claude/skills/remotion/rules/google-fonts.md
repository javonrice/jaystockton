---
name: google-fonts
description: Loading Google Fonts in Remotion using @remotion/google-fonts
metadata:
  tags: fonts, google-fonts, typography
---

# Using Google Fonts in Remotion

Google Fonts is the recommended way to load fonts in Remotion via the `@remotion/google-fonts` package.

## Prerequisites

Install the package:

```bash
npx remotion add @remotion/google-fonts # If project uses npm
bunx remotion add @remotion/google-fonts # If project uses bun
yarn remotion add @remotion/google-fonts # If project uses yarn
pnpm exec remotion add @remotion/google-fonts # If project uses pnpm
```

## Basic Usage

Import and call `loadFont()` from the specific font module:

```tsx
import { loadFont } from "@remotion/google-fonts/Inter";

const { fontFamily } = loadFont();

export const MyComposition = () => {
  return (
    <div style={{ fontFamily }}>
      Hello World
    </div>
  );
};
```

The `loadFont()` function returns a `fontFamily` value and automatically blocks rendering until the font is ready.

## Optimizing Bundle Size

Specify only the weights and subsets you need to reduce file size:

```tsx
import { loadFont } from "@remotion/google-fonts/Inter";

const { fontFamily } = loadFont("normal", {
  weights: ["400", "700"],
  subsets: ["latin"],
});
```

## Best Practices

Call `loadFont()` at the top level of components or in separate files imported early. This approach is type-safe and automatically blocks rendering until the font is ready, preventing layout shifts or flash of unstyled text.
