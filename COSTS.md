# Cost and timing evidence

Source is the local `runs.jsonl` on 24 November 2026, East Africa Time. The table shows the successful synthetic provider calls. Each row is a single observation, so it provides no estimate of average production latency.

| Stage | Model and workload | Successful calls | Recorded latency | Recorded USD | GPU minutes |
| --- | --- | ---: | ---: | --- | --- |
| Script smoke test | Gemini 3.5 Flash-Lite, short text reply | 1 | 1.17 s | TODO | TODO |
| Narration smoke test | Gemini 3.8 Flash-Lite TTS, short synthetic line | 1 | 4.39 s | TODO | TODO |
| Keyframe smoke test | FLUX.1 Schnell, four steps | 1 | 3.99 s | TODO | TODO |
| Character reference | FLUX.2 Klein 4B, 480 × 480 synthetic option | 1 | 8.49 s | TODO | TODO |
| Keyframe | FLUX.2 Klein 4B, 1024 × 1024 synthetic keyframe with a reference | 1 | 5.27 s | TODO | TODO |

The log also records three `URLError` entries from the initial smoke run, at 0.09 s, 0.11 s, and 0.11 s, with no provider HTTP status. The later live smoke run succeeded for all three providers. One FLUX.2 keyframe cache hit followed the successful request. Its latency, cost, and GPU minutes are empty because the cache reused an artifact without a provider call.

Each JSONL record includes `ts`, `stage`, `shot_id`, `model`, `params`, `seed`, `input_hash`, `latency_s`, `cost_estimate_usd`, `gpu_minutes`, `status`, `cache_hit`, and `error`. Latency is recorded in seconds. Empty cost and GPU fields indicate missing measurements.

## Recorded provider latency

The [reviewed snapshot](evidence/runs.jsonl) contains 53 successful provider calls, 19 failed attempts, and 207 cache hits. The table includes successful attempts across both smoke tests and production work. It excludes cache hits and retry delays.

| Stage and model | Successful calls | Median | Range |
| --- | ---: | ---: | ---: |
| Text · Gemini 3.5 Flash-Lite | 1 | 1.17 s | 1.17 s |
| Narration · Gemini 3.8 Flash-Lite TTS | 13 | 4.83 s | 3.99–5.95 s |
| Keyframes · FLUX.1 Schnell | 1 | 3.99 s | 3.99 s |
| Keyframes · FLUX.2 Klein 4B | 29 | 7.61 s | 3.62–19.12 s |
| Character references · FLUX.2 Klein 4B | 9 | 10.04 s | 7.93–14.92 s |

## Pending measurements

| Measurement | Evidence needed |
| --- | --- |
| Provider list-price equivalents | TODO. Record Gemini token usage and Cloudflare usage units, then apply the rate for the model and date. The logged request settings alone do not establish metered usage. |
| Actual billed spend | TODO. Check provider billing or usage records for the project. The current JSONL has no populated USD fields. |
| Wan and ACE-Step runtime and GPU minutes | TODO. Run the GPU notebooks and import their timing sidecars. |
| Ken Burns, radio, and final assembly wall time | TODO. Measure the local FFmpeg runs. The current log does not record these timings. |
| Real film total | TODO. Measure the first approved film run and a repeat run to capture generation time and the effect of caching. |
