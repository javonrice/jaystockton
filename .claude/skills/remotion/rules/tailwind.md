---
name: tailwind
description: Using TailwindCSS in Remotion
metadata:
  tags: tailwind, css, styling
---

# TailwindCSS in Remotion

TailwindCSS can be used in Remotion projects where it is already installed.

## Setup

Before using TailwindCSS, install and enable it in your Remotion project. Follow the Remotion docs for complete setup instructions.

## Critical Restriction

Do NOT use `transition-*` or `animate-*` Tailwind classes. These will not render correctly.

Always animate using the `useCurrentFrame()` hook instead:

```tsx
// WRONG - will not render correctly
<div className="transition-opacity animate-fade-in">Content</div>

// CORRECT - use useCurrentFrame()
import { useCurrentFrame, interpolate } from "remotion";

const frame = useCurrentFrame();
const opacity = interpolate(frame, [0, 30], [0, 1], {
  extrapolateRight: "clamp",
});

<div className="bg-blue-500 text-white p-4" style={{ opacity }}>
  Content
</div>
```

## What Works

Static Tailwind utility classes work fine:
- Layout: `flex`, `grid`, `absolute`, `relative`
- Spacing: `p-4`, `m-2`, `gap-4`
- Colors: `bg-blue-500`, `text-white`
- Typography: `text-xl`, `font-bold`
- Sizing: `w-full`, `h-screen`
- Borders: `rounded-lg`, `border`
