# Film pipeline architecture

The local Python CLI builds *From Rural Ethiopia to Addis Ababa* from [storyboard.json](storyboard.json) and [config.yaml](config.yaml). The storyboard supplies shot order, narration, music and visual prompts, reference paths, and seeds. The configuration supplies model IDs, endpoints, output paths, and render settings. Every CLI stage that consumes the storyboard validates it first. The [schema](schema/storyboard.schema.json) checks the document structure, and the validator detects duplicate shot IDs used by filenames, cache entries, and notebook imports.

## Stage flow

| Step | Inputs and outputs |
| --- | --- |
| Provider smoke test | Sends three synthetic requests to Gemini text, Gemini TTS, and FLUX.1 Schnell. The text probe checks provider access. Film narration comes from the storyboard. |
| Narration | Gemini 3.8 Flash-Lite TTS generates one 24 kHz mono PCM WAV per shot. The stage checks the WAV before caching it. |
| Character references | FLUX.2 Klein 4B renders four seeded JPEG options. The operator picks one, which the CLI copies to `references/golden.jpg`. |
| Keyframes | FLUX.2 Klein 4B receives the shot prompt, shared style and character descriptions, and the approved reference. Outputs are individual JPEGs under `outputs/keyframes/`. |
| Picture clips | The shots stage uses a matching imported Wan clip when available. It prefers 720p over 480p and falls back to FFmpeg Ken Burns motion from the keyframe. |
| Score | An ACE-Step notebook produces three seeded instrumental WAVs from the music brief. After import, the operator chooses one. Assembly uses a synthesized placeholder when a selected score is unavailable. |
| Assembly | FFmpeg times each shot against the measured WAV, trims clip boundaries, and holds the last frame if picture runs short. It mixes and ducks the score under the voice, normalizes in two passes, burns in captions, and adds the “Made with AI” card. The bundle contains 9:16 and 16:9 H.264/AAC MP4s at 24 fps and an SRT. |

The radio cut shares the narration and caption timing code. It renders a black picture with a quiet synthesized score and a default subtitle track so listeners can review the story before the picture is ready.

## Cache and notebook handoff

The [shared utilities](pipeline/utils.py) hash canonical JSON settings and SHA-256 digests of relevant input files. The JSON cache index maps a stage, item ID, and input hash to a completed artifact. Cache writes use a sidecar lock and atomic replacement. A record whose file is missing is treated as a miss.

- Editing one narration line invalidates that shot's WAV and the assembled outputs. Changing one motion prompt invalidates matching Wan imports for that shot. Changing the golden reference invalidates the keyframes built from it.
- The Wan export contains the selected storyboard shots, their keyframes, and a manifest. The music export contains the caption and three candidate contracts. Notebook runners save the media and timing sidecar for each completed item.
- [GPU import](pipeline/import_gpu_outputs.py) checks the sidecar against current source inputs, verifies the media hash, and uses FFprobe to check the artifact. Successfully imported clips and tracks are reusable through the cache.

## Failures and verification

Provider stages retry HTTP 429, HTTP 5xx, and timeouts with exponential backoff and jitter, up to three attempts. If narration or keyframe generation still fails, the stage reports the item and leaves previously completed items available for the next run. The smoke test makes a single attempt per provider to expose connection and configuration errors.

Model attempts, model-output cache hits, and accepted GPU imports use the JSONL event format in [COSTS.md](COSTS.md). Requests read credentials from the local environment. The run log records input hashes, selected numeric settings, and sanitized error types or HTTP status codes. Local FFmpeg stages do not report elapsed time in that log.

Live synthetic probes verified Gemini text, Gemini speech, and both configured FLUX models. The first real film built locally at 82.5 seconds. A clean local clone regenerated both full-size exports by replaying the ten saved FLUX and Gemini TTS responses against empty outputs. This verified local reproducibility without a second round of provider calls. The Wan and ACE-Step notebook paths have local fixture coverage, with GPU execution pending.
