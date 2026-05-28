---
name: subtitles
description: Working with captions and subtitles in Remotion
metadata:
  tags: captions, subtitles, srt, display, transcribe
---

# Captions and Subtitles in Remotion

Captions must be processed using JSON format with the `Caption` type from `@remotion/captions`.

## Caption Format

```ts
import type { Caption } from "@remotion/captions";

const caption: Caption = {
  text: "Hello World",        // The caption content
  startMs: 0,                 // Start time in milliseconds
  endMs: 2000,                // End time in milliseconds
  timestampMs: null,          // Optional timestamp
  confidence: null,           // Optional confidence metric
};
```

## Main Workflows

### 1. Generating Captions

Transcribe audio or video files to generate captions. See [transcribe-captions.md](./transcribe-captions.md) for details.

### 2. Displaying Captions

Render captions within your video composition. See [display-captions.md](./display-captions.md) for details.

### 3. Importing .srt Files

Convert existing `.srt` subtitle files to the Caption format. See [import-srt-captions.md](./import-srt-captions.md) for details.
