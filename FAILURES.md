# Failure journal

| Observed blocker | What was tried | Result |
| --- | --- | --- |
| The cached assembly stopped at shot 5 after its image prompt changed. | Checked all ten shot inputs. A live attempt returned a Cloudflare request `URLError` without an HTTP status. Checked the earlier bus prompt against the same approved reference and shared prompts. | The earlier prompt matched a cached keyframe and was restored in the storyboard. The full entry point found matching inputs and both exports. The rewritten bus prompt still needs a successful live generation if selected for a later cut. |
| The run log records Gemini narration HTTP 429 responses. | The narration stage inspects provider retry information, backs off for retryable throttling, and surfaces a daily quota error without repeated requests. | The run log also contains successful narration calls. The current cut has all ten narration assets cached. |
| The run log records FLUX HTTP 400 responses. | The keyframe code logs the HTTP status and stops the affected item while preserving complete assets. | The recorded HTTP status alone does not establish the specific cause. The current storyboard has a matching cached keyframe for every shot. |
