---
name: calculate-metadata
description: Dynamically set composition duration, dimensions, and props using calculateMetadata
metadata:
  tags: metadata, duration, dimensions, dynamic, props
---

# Dynamic Metadata with calculateMetadata

Use `calculateMetadata` to dynamically configure composition properties before rendering. It accepts props and an abort signal, returning optional overrides for composition settings.

## Return Options

The function can override any of these composition properties:
- `durationInFrames`
- `width` and `height`
- `fps`
- `props` (transformed values)
- `defaultOutName`
- `defaultCodec`

All return fields are optional, allowing partial updates to composition configuration.

## Dynamic Duration from Video

Use the `getVideoDuration` skill to get the video duration and set composition length accordingly:

```tsx
import { CalculateMetadataFunction, staticFile } from "remotion";
import { Input, ALL_FORMATS, UrlSource } from "mediabunny";

const getVideoDuration = async (src: string) => {
  const input = new Input({
    formats: ALL_FORMATS,
    source: new UrlSource(src, { getRetryDelay: () => null }),
  });
  return await input.computeDuration();
};

export const calculateMetadata: CalculateMetadataFunction<Props> = async ({
  props,
  abortSignal,
}) => {
  const duration = await getVideoDuration(staticFile(props.videoFile));

  return {
    durationInFrames: Math.ceil(duration * 30),
    props,
  };
};
```

## Fetching Data

Fetch data or transform props before rendering with built-in request cancellation support:

```tsx
import { CalculateMetadataFunction } from "remotion";

export const calculateMetadata: CalculateMetadataFunction<Props> = async ({
  props,
  abortSignal,
}) => {
  const data = await fetch(`https://api.example.com/video/${props.videoId}`, {
    signal: abortSignal,
  }).then((res) => res.json());

  return {
    durationInFrames: Math.ceil(data.duration * 30),
    props: {
      ...props,
      videoUrl: data.url,
    },
    width: 1080,
    height: 1080,
  };
};
```

## Matching Video Dimensions

Match output dimensions to source video specifications:

```tsx
export const calculateMetadata: CalculateMetadataFunction<Props> = async ({
  props,
}) => {
  // Use getVideoMetadata or mediabunny to get dimensions
  const { width, height } = await getVideoDimensions(staticFile(props.src));

  return { width, height };
};
```
