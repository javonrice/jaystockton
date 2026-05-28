---
name: transcribe-captions
description: Transcribing audio to generate captions using Whisper.cpp in Remotion
metadata:
  tags: captions, transcription, whisper, audio, speech-to-text
---

# Transcribing Audio to Generate Captions in Remotion

Use `@remotion/install-whisper-cpp` to transcribe audio for caption generation.

## Prerequisites

```bash
npx remotion add @remotion/install-whisper-cpp
```

## Workflow

### Step 1: Install Whisper.cpp

```ts
import { installWhisperCpp } from "@remotion/install-whisper-cpp";

await installWhisperCpp({ version: "1.5.5", to: "./whisper.cpp" });
```

### Step 2: Download a language model

```ts
import { downloadWhisperModel } from "@remotion/install-whisper-cpp";

await downloadWhisperModel({ model: "medium.en", folder: "./whisper.cpp" });
```

### Step 3: Convert audio to 16KHz WAV (if needed)

```bash
npx remotion ffmpeg -i public/audio.mp3 -ar 16000 -ac 1 public/audio-16k.wav
```

### Step 4: Transcribe

```ts
import { transcribe } from "@remotion/install-whisper-cpp";
import { toCaptions } from "@remotion/captions";

const { transcription } = await transcribe({
  inputPath: "./public/audio-16k.wav",
  whisperPath: "./whisper.cpp",
  model: "medium.en",
});

const { captions } = toCaptions({ transcription });

// Save as JSON for use in Remotion
import { writeFileSync } from "fs";
writeFileSync("public/captions.json", JSON.stringify(captions));
```

## Notes

- Transcribe each clip individually and create multiple JSON files.
- Store output JSON files in `public/` so Remotion can access them via `staticFile()`.
- For displaying the captions, see [display-captions.md](./display-captions.md).
