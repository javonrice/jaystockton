---
name: images
description: Sizing, positioning, and working with images in Remotion
metadata:
  tags: images, img, sizing, dimensions, dynamic
---

# Using Images in Remotion

## Basic Usage

Use the `<Img>` component from `remotion` to display images:

```tsx
import { Img, staticFile } from "remotion";

export const MyComposition = () => {
  return <Img src={staticFile("logo.png")} style={{ width: 100, height: 100 }} />;
};
```

## Styling Images

Control dimensions and positioning through the `style` prop:

```tsx
<Img
  src={staticFile("photo.jpg")}
  style={{
    width: 500,
    height: 300,
    position: "absolute",
    top: 100,
    left: 50,
    objectFit: "cover",
  }}
/>
```

## Dynamic Image References

Use template literals for dynamic file references:

```tsx
// Frame-by-frame animation sequences
const frame = useCurrentFrame();
<Img src={staticFile(`frames/frame-${String(frame).padStart(4, "0")}.png`)} />

// User-specific assets based on props
<Img src={staticFile(`avatars/${props.userId}.png`)} />

// Conditional graphics
<Img src={staticFile(isActive ? "icon-on.png" : "icon-off.png")} />
```

## Getting Image Dimensions

Use `getImageDimensions()` to retrieve width and height for aspect ratio calculations:

```tsx
import { getImageDimensions } from "@remotion/media-utils";
import { staticFile, CalculateMetadataFunction } from "remotion";

const calculateMetadata: CalculateMetadataFunction<Props> = async ({ props }) => {
  const { width, height } = await getImageDimensions(staticFile(props.imageSrc));
  return { width, height };
};
```
