# Experiments

## Recovery check

| Hypothesis tested | Change | Observed result |
| --- | --- | --- |
| The edited bus prompt is the only reason the current storyboard misses the model cache. | Checked keyframe and narration inputs for each shot independently, then tried the earlier bus prompt with the current shared style and character settings. | All ten narration inputs and nine keyframes matched. The earlier bus prompt matched the remaining cached keyframe. The full entry point resolved the 86.46-second export pair using cached assets. This checks reproducibility and says nothing about picture preference. |
| A shot-specific narration edit should change one audio input and keep all pictures reusable. | Compared the current storyboard with an in-memory copy using the earlier shot 9 narration. Resolved both using the same cache. | Only shot 9 resolved to a different WAV. The nine other WAV paths and all ten keyframe paths matched. Both lines were already cached, so this test made no live model call. |
| Matching model assets are sufficient to reproduce the exact current film locally. | Ran assembly in an isolated workdir seeded with the storyboard, approved reference, cached keyframes and narration. Excluded picture clips and final exports. | FFmpeg regenerated ten clips. SHA-256 matched for both MP4s and the SRT against the existing export bundle. |

## Post-review checks on the 86.46-second cut

Both picture checks sampled the same opening frame at 00:03 in each export. They describe what appeared on screen.

| Hypothesis tested | Comparison | Observed result and next decision |
| --- | --- | --- |
| The opening character reference carries through as a single coherent scene in both crops. | Compared the horizontal and vertical frame at 00:03 against the storyboard's empty landscape prompt. | Three views of the same character appear in the horizontal cut. The vertical crop centers one profile but leaves partial faces at the edges. Test a landscape keyframe without the turnaround reference for this no-character shot. |
| The same opening caption fits comfortably in both crops. | Compared the burned-in first caption at the same moment in both exports. | The sampled caption uses two lines horizontally and four vertically. Test shorter cue segments for mobile and check that viewers can finish reading without pausing. |
| Both exports carry the same loudness after AAC encoding. | Ran FFmpeg's loudness measurement on each finished MP4. | Both measured −14.10 LUFS integrated, −1.00 dBTP, and 4.10 LU loudness range. Keep the current loudness settings for the next audience test. |

## Filmmaker notes

Add actual trial results using the columns above, with the shot or version, seed where applicable, and supporting log events. The rubric asks for at least ten logged experiments. Planned trials and repeated cache hits by themselves do not count as results.

The planned Heritage Studio usability experiment with three non-developers is awaiting participant feedback.
