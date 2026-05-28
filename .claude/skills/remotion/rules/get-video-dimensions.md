---
name: get-video-dimensions
description: Getting the width and height of a video file with Mediabunny
metadata:
  tags: dimensions, video, width, height, resolution
---

# Getting video dimensions with Mediabunny

Mediabunny can extract the dimensions of a video file. It works in browser, Node.js, and Bun environments.

## Getting video dimensions

```tsx
import { Input, ALL_FORMATS, UrlSource } from "mediabunny";

export const getVideoDimensions = async (src: string) => {
  const input = new Input({
    formats: ALL_FORMATS,
    source: new UrlSource(src, {
      getRetryDelay: () => null,
    }),
  });

  const primaryVideoTrack = await input.primaryVideoTrack();
  const { displayWidth, displayHeight } = primaryVideoTrack;
  return { width: displayWidth, height: displayHeight };
};
```

## Usage

```tsx
const { width, height } = await getVideoDimensions("https://remotion.media/video.mp4");
console.log(width, height); // e.g. 1920 1080
```

## Video files from the public/ directory

Make sure to wrap the file path in `staticFile()`:

```tsx
import { staticFile } from "remotion";

const { width, height } = await getVideoDimensions(staticFile("video.mp4"));
```

## In Node.js and Bun

Use `FileSource` instead of `UrlSource`:

```tsx
import { Input, ALL_FORMATS, FileSource } from "mediabunny";

const input = new Input({
  formats: ALL_FORMATS,
  source: new FileSource(file), // File object from input or drag-drop
});

const primaryVideoTrack = await input.primaryVideoTrack();
```
