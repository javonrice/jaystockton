---
name: transparent-videos
description: Rendering videos with transparency (alpha channel) in Remotion
metadata:
  tags: transparency, alpha, prores, webm, vp9
---

# Transparent Videos in Remotion

Remotion supports rendering transparent videos through two primary methods.

## ProRes (for video editing software)

```bash
npx remotion render MyComposition out/video.mov --image-format=png --pixel-format=yuva444p10le --codec=prores --prores-profile=4444
```

Best for professional workflows and video editing software integration. Preserves maximum quality.

## WebM/VP9 (for browser playback)

```bash
npx remotion render MyComposition out/video.webm --image-format=png --pixel-format=yuva420p --codec=vp9
```

Optimized for web distribution and browser playback.

## Configuration Methods

### CLI arguments (one-off renders)

Pass flags directly on the command line as shown above.

### remotion.config.ts (studio defaults)

```ts
import { Config } from "@remotion/cli/config";

Config.setImageFormat("png");
Config.setPixelFormat("yuva444p10le");
Config.setCodec("prores");
Config.setProResProfile("4444");
```

Requires a studio restart to take effect.

### calculateMetadata (per-composition defaults)

```tsx
import { CalculateMetadataFunction } from "remotion";

export const calculateMetadata: CalculateMetadataFunction<Props> = async () => {
  return {
    defaultCodec: "prores",
  };
};
```
