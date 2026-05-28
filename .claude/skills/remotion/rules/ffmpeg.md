---
name: ffmpeg
description: Using FFmpeg in Remotion for video trimming, silence detection, and other operations
metadata:
  tags: ffmpeg, trim, video, audio, silence
---

# Using FFmpeg in Remotion

`ffmpeg` and `ffprobe` do not need to be installed separately. They are available via the `npx remotion ffmpeg` and `npx remotion ffprobe` commands.

## Trimming Videos

### Recommended Method

Use the `<Video>` component's `trimBefore` and `trimAfter` properties. This avoids re-encoding and allows adjustments without regenerating files.

```tsx
import { Video } from "@remotion/media";
import { staticFile, useVideoConfig } from "remotion";

const { fps } = useVideoConfig();

<Video
  src={staticFile("video.mp4")}
  trimBefore={2 * fps}  // Skip first 2 seconds
  trimAfter={10 * fps}  // End at 10 second mark
/>
```

### Alternative Method (FFmpeg CLI)

Apply FFmpeg command-line trimming when you need a standalone trimmed file. This requires re-encoding:

```bash
npx remotion ffmpeg -i public/video.mp4 -ss 00:00:02 -to 00:00:10 -c:v libx264 -c:a aac public/trimmed.mp4
```

The component-based approach is preferred for most workflows due to its non-destructive nature and flexibility.

## Probing Video Information

Use `npx remotion ffprobe` to get video metadata:

```bash
npx remotion ffprobe public/video.mp4
```

## Converting Audio Format

Convert audio to 16KHz WAV for Whisper transcription:

```bash
npx remotion ffmpeg -i public/audio.mp3 -ar 16000 -ac 1 public/audio-16k.wav
```
