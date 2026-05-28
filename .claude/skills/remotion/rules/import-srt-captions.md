---
name: import-srt-captions
description: Importing .srt subtitle files into Remotion using @remotion/captions
metadata:
  tags: captions, subtitles, srt, import
---

# Importing .srt Subtitles into Remotion

## Prerequisites

Install `@remotion/captions`:

```bash
npx remotion add @remotion/captions # If project uses npm
bunx remotion add @remotion/captions # If project uses bun
yarn remotion add @remotion/captions # If project uses yarn
pnpm exec remotion add @remotion/captions # If project uses pnpm
```

## Implementation

Place the `.srt` file in your project's `public/` folder, then fetch and parse it:

```tsx
import { useState, useEffect, useCallback } from "react";
import { staticFile, useDelayRender, continueRender, cancelRender } from "remotion";
import { parseSrt } from "@remotion/captions";
import type { Caption } from "@remotion/captions";

export const MyComponent: React.FC = () => {
  const [captions, setCaptions] = useState<Caption[] | null>(null);
  const [handle] = useState(() => useDelayRender("Loading captions"));

  const fetchCaptions = useCallback(async () => {
    try {
      const response = await fetch(staticFile("subtitles.srt"));
      const text = await response.text();
      const { captions: parsed } = parseSrt({ input: text });
      setCaptions(parsed);
      continueRender(handle);
    } catch (e) {
      cancelRender(e);
    }
  }, [handle]);

  useEffect(() => {
    fetchCaptions();
  }, [fetchCaptions]);

  if (!captions) return null;

  // Use captions here
  return null;
};
```

## Remote URLs

Remote subtitle files are also supported — fetch from an external URL instead of `staticFile()`:

```tsx
const response = await fetch("https://example.com/subtitles.srt");
```

## Output Format

`parseSrt()` returns captions in the `Caption` format, compatible with all utilities in `@remotion/captions`, including `createTikTokStyleCaptions()` for display.
