# Ethics and consent

## Recorded consent

On 24 November 2026 (East Africa Time), the filmmaker confirmed consent in the project conversation to be depicted as an AI-generated illustration in *From Rural Ethiopia to Addis Ababa* and to have a synthetic narrator tell his story in the first person. He also agreed to record that consent here. The supplied portrait informed the written character description. The image itself was kept local.

The mother's consent is pending. Shot 4 shows the bag handoff without faces, and she stays offscreen during the phone call in shot 9.

The filmmaker also authorized sending the written character description to Cloudflare FLUX to generate four reference options. The portrait itself was excluded from those requests.

## Labelling and licences

The verified local cut includes a “Made with AI” end card. Use the platform's AI disclosure when uploading the film and keep a record of the applied label with the published version.

| Asset in the verified cut | Source and terms |
| --- | --- |
| Approved character reference and shot illustrations | Generated through Cloudflare Workers AI with FLUX.2 Klein 4B. Black Forest Labs publishes its model weights under Apache 2.0. Cloudflare links the terms for the hosted model. [Model card](https://huggingface.co/black-forest-labs/FLUX.2-klein-4B) · [Hosted endpoint](https://developers.cloudflare.com/workers-ai/models/flux-2-klein-4b/) |
| English narration | Generated with a Gemini API synthetic voice. Google states that it does not claim ownership of original generated content and that the user is responsible for its use. [Gemini API terms](https://ai.google.dev/gemini-api/terms#use-generated) |
| Temporary score | Synthesized locally from sine tones in the pipeline. [Synthesis source](pipeline/radio.py) |
| Motion, captions, and end card | Rendered locally by FFmpeg. FFmpeg's software licence depends on its build options. The Windows overlay uses the installed Arial font when available. [FFmpeg licensing](https://www.ffmpeg.org/legal.html) · [Assembly code](pipeline/assemble.py) |

The verified cut uses FFmpeg pan-and-zoom for all ten shots. If a later cut imports Wan motion or an ACE-Step score, record the exact model, checkpoint, and applicable terms for those assets before release.
