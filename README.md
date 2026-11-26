# Heritage Studio

**From Rural Ethiopia to Addis Ababa** is an 86.46-second animated short about learning to code on a borrowed laptop and growing into a software developer. It was made for young Ethiopian developers and students, as well as family and friends. A loading ring follows the journey from the countryside to the city, and a promise to call home gives the film its ending.

The repository turns a [ten-shot storyboard](storyboard.json) into English narration, illustrated keyframes, animated shots, and captioned exports. The verified cut uses Gemini narration, FLUX illustrations, FFmpeg pan-and-zoom, and a temporary synthesized score ducked under the voice. It includes a **Made with AI** end card.

| Output | Format |
| --- | --- |
| Vertical film | 1080 × 1920 MP4, 9:16 |
| Horizontal film | 1920 × 1080 MP4, 16:9 |
| English captions | Burned into both videos and available as a separate SRT |

[Build verification and submission status](EVIDENCE.md)

## Build the film

Run these commands from the repository root. You need Python 3.11 or newer, and `ffmpeg` and `ffprobe` on your PATH. Use an FFmpeg build with `libx264`, `subtitles`, and `drawtext` support.

Copy [`.env.example`](.env.example) to `.env` and fill in `GEMINI_API_KEY`, `CLOUDFLARE_ACCOUNT_ID`, and `CLOUDFLARE_API_TOKEN`. Keep `.env` local. The build uses the approved [character reference](references/golden.jpg) included in the repository. Uncached narration and keyframes require provider access and available quota.

**With GNU Make**

```bash
cp .env.example .env
# Fill in the provider credentials in .env.
make setup
make film
```

**With Windows PowerShell**

```powershell
Copy-Item .env.example .env
# Fill in the provider credentials in .env.
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pipeline.assemble
```

After setup, `make film` or the final PowerShell command validates the storyboard, resolves or generates the model assets, and prints the exact paths to `vertical.mp4`, `horizontal.mp4`, and `captions.srt` under `outputs/final/<input-hash>/`. The checkout contains the source inputs. Generated media and the working cache are stored locally.

## Iterate on the cut

| Task | GNU Make | Python module |
| --- | --- | --- |
| Validate the storyboard | `make validate` | `python -m pipeline.validate` |
| Probe the configured providers | `make smoke` | `python -m pipeline.smoke` |
| Build the captioned radio cut | `make radio` | `python -m pipeline.radio` |
| Generate or reuse the keyframes | `make keyframes` | `python -m pipeline.keyframes` |
| Refresh shot 5 after editing it and rebuild the film | `make shot ID=5` | `python -m pipeline.assemble --shot 5` |
| Assemble from matching cached keyframes and narration | `make stage S=assemble` | `python -m pipeline.assemble --cached-only` |

Use the Python interpreter from your virtual environment for the module commands. For the shot-specific build, the other shots must already have matching cached assets. To isolate a project, put its storyboard and approved reference in a separate directory and pass `--workdir path/to/job` or `WORKDIR=path/to/job` to Make.

The pipeline hashes the inputs to each item, including relevant prompts, model settings, reference images, and upstream files. Changing one narration line invalidates that shot's audio and the final edit. Transient provider failures are retried, and completed assets remain available for the next run. The local `runs.jsonl` records provider attempts and cache hits. See the [architecture](ARCHITECTURE.md) for the stage contracts.

### Optional GPU motion and score

The default build can use pan-and-zoom and a synthesized score. A matching Wan clip is preferred over pan-and-zoom for its shot, and a selected ACE-Step track replaces the temporary score.

1. **Wan 2.2.** Generate keyframes, then run `python -m pipeline.shots --shot 5 --export-wan outputs/wan-bundle`. Add `--quality final` for a 720p job. Move the bundle and [Wan runner](notebooks/shots_wan22.py) to a GPU environment. The runner takes the bundle and output directories as positional arguments. Download the clips with their JSON sidecars and run `python -m pipeline.import_gpu_outputs path/to/wan-clips`.
2. **ACE-Step.** Run `python -m pipeline.music --export-ace outputs/ace-music.json`. In an ACE-Step GPU environment, run the [music runner](notebooks/music_acestep.py) with the manifest and candidates directory. Download the WAVs and their JSON sidecars, run `python -m pipeline.import_gpu_outputs --stage music path/to/music-candidates`, then audition the tracks and select one with `python -m pipeline.music --select 2`, using the number of your chosen track.

## Run the local web app

The optional **Heritage Studio** web app reuses the film pipeline. It guides a user through consent, story entry, storyboard approval, radio-cut review, and film export.

Start the API from the repository root using the project virtual environment:

```bash
python -m pip install -r studio/api/requirements.txt
python -m uvicorn studio.api.main:app --host 127.0.0.1 --port 8000
```

In a second terminal, start the frontend with Node.js and npm:

```bash
cd studio/web
npm ci
npm run dev
```

Open [Heritage Studio](http://127.0.0.1:3000) or the [API docs](http://127.0.0.1:8000/docs). If the API URL changes, set `NEXT_PUBLIC_STUDIO_API_URL` for the frontend.

## Tests and submission evidence

```bash
python -m unittest discover -s tests -v
python -m pip install -r studio/api/requirements-dev.txt
python -m unittest discover -s studio/api/tests -v
```

From `studio/web`, run `npm run typecheck` after `npm ci`.

- [Design and audience feedback](DESIGN.md)
- [Experiments](EXPERIMENTS.md) and [failure journal](FAILURES.md)
- [Measured latency and open cost items](COSTS.md) and [reviewed run log](evidence/runs.jsonl)
- [Consent record](ETHICS.md) and [asset sources and submission checklist](EVIDENCE.md)
- [Draft project report](Heritage%20Short%20Report.docx)
