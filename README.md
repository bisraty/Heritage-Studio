# Hirna to Addis: an AI-made heritage short

A 60-90 second short film about my journey from Hirna, a rural area in Ethiopia, to Addis Ababa, and growing into a software developer. Tone: mostly funny, with a heartfelt ending. Narration in English, English subtitles, an original score ducked under the voice, and a visible "Made with AI" end card. Exported in 9:16 and 16:9.

The film is one output. The pipeline is the real deliverable: a stranger should be able to clone this repo, run one command, and regenerate the film from `storyboard.json`.

> **For Codex:** this README is also your brief. Read the whole file first, then follow "Instructions for the coding agent" at the bottom. Ask me before making decisions that are not covered here.

---

## One command

```bash
cp .env.example .env        # add GEMINI_API_KEY and CLOUDFLARE_* keys
make setup                  # create venv, install deps, check ffmpeg
make film                   # validate storyboard, run all stages, export both ratios
```

The film command uses the approved `references/golden.jpg` and credentials in `.env`. Matching Wan clips and the selected ACE-Step score are optional inputs. The pipeline can build with Ken Burns clips and a temporary synthesized score while the notebook assets are pending. Each build writes `vertical.mp4`, `horizontal.mp4`, and `captions.srt` together under `outputs/final/`.

On Windows without GNU Make, run `\.venv\Scripts\python.exe -m pipeline.assemble`. Use `--cached-only` to assemble from existing narration and keyframes, or `--shot 5` to refresh shot 5 and rebuild the exports using the other shots' cached inputs.

For a separate job directory, put its `storyboard.json` and approved `references/golden.jpg` there, then run `make film WORKDIR=jobs/example` or `python -m pipeline.assemble --workdir jobs/example`. The job owns its references, outputs, cache, and run log. It uses the repository configuration unless it provides its own `config.yaml`. Credentials come from the process environment or the repository's `.env`.

Other commands:

```bash
make validate               # validate storyboard.json against the schema only
make smoke                  # call each provider once, log latency to runs.jsonl
make stage S=keyframes      # run one stage (script|keyframes|shots|music|narration|assemble)
make references             # generate four character reference options
make reference N=2          # save option 2 as references/golden.jpg
make shot ID=5              # regenerate only shot 5 (all stages that touch it)
make radio                  # narration over placeholder music on black (user test 1)
make clean-cache            # delete the cache index, keep outputs
```

---

## Design

- **Audience:** young Ethiopian developers and students outside the big cities, plus family and followers. Watched on phones, vertical first.
- **Intent:** viewers laugh, then think "if he did it from Hirna, I can too."
- **Look:** warm hand-painted storybook illustration, not photoreal. Friendlier, funnier, easier to keep consistent.
- **Running motif:** a loading/buffering circle appears in many shots (sky, bus window, traffic). It pays off in the final joke and the end card.
- **Callback:** in shot 4 his mother says "Call me when you arrive." In shot 9 he finally calls her.

Details, the user tests and what they changed go in `DESIGN.md`.

---

## Pipeline

`storyboard.json` is the single contract. Every stage reads it and writes its own output. Changing one shot regenerates only that shot.

```
storyboard.json
   |
   +--> script      (optional Gemini Flash call: refine narration, translate subtitles)
   +--> narration   Gemini TTS, one audio file per shot
   +--> keyframes   FLUX on Cloudflare Workers AI, one still per shot
   +--> shots       Wan 2.2 clips (made on Kaggle) or FFmpeg Ken Burns fallback
   +--> music       ACE-Step 1.5 candidates (made on Kaggle/Colab), one chosen
   +--> assemble    FFmpeg: cut, duck, subtitles, loudnorm, end card, export 9:16 + 16:9
```

| Stage | Tool | Runs where | Output |
|---|---|---|---|
| script | Gemini Flash / Flash-Lite | Gemini API | refined text in storyboard |
| narration | Gemini TTS | Gemini API | `outputs/narration/` |
| keyframes | FLUX.2 klein or FLUX.1 schnell | Cloudflare Workers AI | `outputs/keyframes/` |
| shots | Wan 2.2 TI2V-5B | Kaggle notebook (2x T4) | `outputs/shots/` |
| shots (fallback) | FFmpeg zoompan | local | `outputs/shots/` |
| music | ACE-Step 1.5 | Kaggle or Colab | `outputs/music/` |
| assemble | FFmpeg | local | `outputs/final/` |

Model names, parameters and endpoints live in `config.yaml`, not in code, because free tiers and model names change.

### Stage rules (all stages)

1. **Validate first.** Every run validates `storyboard.json` against `schema/storyboard.schema.json` and fails fast with a readable error.
2. **Cache by input hash.** Hash the inputs that affect a shot (prompt, seed, model, params, reference files, upstream file hashes). Save outputs as `outputs/<stage>/<shot_id>_<hash>.<ext>` and record them in `outputs/cache_index.json`. If the hash exists, skip the call and log a `cache_hit`.
3. **Retry with backoff.** Retry transient errors (429, 5xx, timeouts) with exponential backoff and jitter. Max 3 attempts per shot, then use the fallback and log the failure.
4. **Log every model call** as one JSON line in `runs.jsonl`:
   `ts, stage, shot_id, model, params, seed, input_hash, latency_s, cost_estimate_usd, gpu_minutes, status, cache_hit, error`
5. **No secrets in the repo.** Keys live in `.env` (gitignored). Commit `.env.example` only.
6. **Idempotent and resumable.** Save outputs as each item finishes, so a crash or quota stop loses nothing.

### Kaggle and Colab jobs (shots, music)

GPU stages run in a notebook, not through an API. Provide:

- `notebooks/shots_wan22.py`: reads `storyboard.json` and the keyframes, runs Wan 2.2 TI2V-5B at 480p for drafts (720p only for chosen shots), and saves each clip as soon as it finishes, with its seed and timing in a sidecar JSON.
- `notebooks/music_acestep.py`: generates 3 instrumental candidates from the music caption and metadata, saved with sidecar JSON.
- `pipeline/import_gpu_outputs.py`: copies downloaded clips and tracks into `outputs/`, verifies their hashes and writes the matching lines to `runs.jsonl` (model, seed, latency, GPU minutes from the sidecar).

If a shot has no Wan clip, `shots.py` creates a Ken Burns clip from the keyframe so the film always builds.

After generating the keyframes, run `make stage S=shots` for the local clips. To try Wan on shot 5, export a bundle with `python -m pipeline.shots --shot 5 --export-wan outputs/wan-bundle`. Add `--quality final` to export a 720p job for a chosen shot. When using PowerShell, run these Python commands with `\.venv\Scripts\python.exe`.

Upload the bundle and `notebooks/shots_wan22.py` to a Kaggle notebook with a GPU attached. Install the notebook dependencies with `%pip install "diffusers>=0.35" transformers accelerate sentencepiece ftfy imageio-ffmpeg`, then run `!python shots_wan22.py /path/to/bundle /kaggle/working/wan-clips`. Each process uses one GPU. On a two-GPU session, `--device 0` and `--device 1` can process disjoint shot selections.

Download the MP4s and their JSON sidecars together, then run `python -m pipeline.import_gpu_outputs path/to/wan-clips`. The shots stage prefers matching 720p imports, then matching 480p imports, then the local Ken Burns clip.

### Assembly details

- Cut picture to the narration: each shot lasts `max(narration_duration + 0.5 s, duration_s)`. Trim weak first and last half-seconds of clips.
- Duck the score with `sidechaincompress` (start at threshold 0.02, ratio 6, attack 300 ms, release 1500 ms).
- Bring narration and music to similar loudness before mixing, then `loudnorm` the final to about -14 LUFS, true peak -1 dB (two-pass).
- Burn in English subtitles: max 2 lines, about 40 characters per line, inside the vertical safe area. Also write a `.srt`.
- Subject sits centre-frame in keyframes, so 9:16 and 16:9 are cropped or padded from the same material.
- End card: 2-3 seconds, reads "Made with AI", added in code (never inside generated images).
- Titles and any on-screen text (such as "Hello World" in shot 3) are drawn in code, not in generated images.
- Export H.264 video + AAC audio, constant frame rate (24 fps), MP4.

---

## Repository layout

```
README.md
storyboard.json            the contract
config.yaml                models, params, paths, ducking settings
schema/                    storyboard.schema.json
pipeline/                  one script per stage + shared utils (hash, cache, log, retry)
notebooks/                 Kaggle/Colab scripts for Wan 2.2 and ACE-Step
outputs/                   generated images, audio, video, final exports
runs.jsonl                 one line per model call
Makefile
.env.example
DESIGN.md                  audience, intent, the two user tests and what changed
ARCHITECTURE.md            stages, contracts, caching, failure handling
EXPERIMENTS.md             hypothesis -> change -> result (target: about 10)
FAILURES.md                what broke, what I tried, what fixed it
COSTS.md                   measured latency and GPU minutes per stage, list-price equivalent
ETHICS.md                  consent record, licences, labelling plan
site/                      optional showcase website (see below)
studio/                    optional Heritage Studio web app: frontend + backend (see below)
jobs/                      one folder per studio job (gitignored): storyboard, consent, uploads, outputs
```

---

## Style and character blocks

Attach both to every image prompt, unchanged, to avoid drift.

**Style block:** warm hand-painted storybook illustration, soft film grain, golden-hour light, earthy greens and terracotta, gentle humor, no text in the image

**Character block:** young Ethiopian man, [HAIR], [GLASSES / NO GLASSES], [BUILD], [SIGNATURE CLOTHING], kind expressive face

Workflow: first generate a character and style reference sheet (4 options, I will pick one), save it as the golden reference, then generate every keyframe against it. For video prompts, describe only motion and camera, since the image already holds the subject.

After recording consent and filling in the character details, run `make references`. Review the four numbered JPEGs under `outputs/references/`, then run `make reference N=<option>` and `make stage S=keyframes`. Keep `references/golden.jpg` with the project so a clean checkout can reuse the choice. Shot-level references are optional JPEGs under 512 × 512 pixels, listed as paths in the storyboard. FLUX.2 klein accepts the selected golden reference plus up to three additional images per shot.

In Windows PowerShell without GNU Make, use `\.venv\Scripts\python.exe -m pipeline.keyframes` with `--reference-options`, `--select-reference 2`, or no arguments for the three steps above. Use `--shot 5` to regenerate only shot 5 if its inputs changed.

---

## Initial storyboard content

Seed `storyboard.json` with these 10 shots. Each shot needs: `id`, `duration_s`, `reason`, `shot_size`, `image_prompt`, `motion_prompt`, `narration`, `music_cue`, `references`, `seed`. Placeholders in [BRACKETS] are filled by me.

| # | Shot | Image prompt (plus style and character blocks) | Motion | Narration | Why |
|---|---|---|---|---|---|
| 1 | Wide | Green highlands of Hirna at sunrise, small house, a loading circle hanging in the sky like a sun | slow push-in, breeze in grass | "I was born in Hirna, where the mornings are green and the internet is a rumour." | Place and motif, first laugh |
| 2 | Medium | The character as a boy at a window with a borrowed laptop, curious | gentle drift, screen glow flickers | "I learned to code on a borrowed laptop, one tiny download at a time." | Sets up the dream |
| 3 | Insert | Close-up of a laptop screen glowing, neighbours peeking in from the sides | slow zoom on screen | "My first program said Hello World. The page took an hour to load. Worth it." | First victory, buffering joke |
| 4 | Medium close-up | His mother handing him a packed bag, warm goodbye (see consent note) | slow push-in | "My mother packed one bag and said, 'Go. Call me when you arrive.'" | Emotional hook for the ending |
| 5 | Wide | Crowded bus on a winding road, laptop on his knees, bags piled on the roof, loading circle on the window | slow pan along the road, gentle sway | "The bus to Addis took all day. My laptop rode on my knees. My dreams rode on the roof." | Bus joke |
| 6 | Wide | Addis Ababa traffic and tall buildings, the character tiny and wide-eyed, loading circle floating over the jam | slow tilt up | "Addis was loud, fast, and full of better developers. I got lost twice. Once on the map." | Traffic joke, scale |
| 7 | Medium | Late-night desk, many coffee cups, code glowing on screen | locked off, subtle light change | "So I coded at night, broke things in the morning, and fixed them by lunch. Repeat." | Persistence |
| 8 | Medium close-up | Confident character holding a phone or laptop showing [APP NAME] | slow push-in | "Years later, I built [APP NAME], and people across Ethiopia use it every day." | The payoff |
| 9 | Medium | Character on a phone call, mother smiling in the green hills (split composition) | slow push-in | "Then I finally called her. 'Mother, I arrived.' If a boy from Hirna can, so can you." | Heartfelt ending, callback |
| 10 | Close-up | Character grinning at a laptop with a loading circle on it | very slow pull-out, then end card | "Now, if you'll excuse me, my page is still loading." | Closing joke, then "Made with AI" |

Target about 7 seconds per shot, one gentle movement each. Final shot lengths are set by the measured narration, not by guesses.

### Music

- **Caption:** warm acoustic instrumental, light Ethiopian-pentatonic feel, gentle percussion, hopeful and playful, no strong lead melody
- **Metadata:** instrumental, about 90 BPM (set in metadata fields, not in the caption)
- **Cues:** soft and curious in shots 1-4, a lift at the goodbye (4), brighter from 5, resolving on 9, a playful stop on 10
- Generate 3 candidates, choose one, record why in `EXPERIMENTS.md`.

Export the music brief with `python -m pipeline.music --export-ace outputs/ace-music.json`. In a GPU notebook, install [ACE-Step 1.5](https://github.com/ace-step/ACE-Step-1.5) following its setup instructions. From that installation, run `uv run python /path/to/music_acestep.py /path/to/ace-music.json /path/to/music-candidates`. The runner saves each WAV and a matching JSON sidecar before moving to the next candidate.

Download the WAVs and sidecars together. Run `python -m pipeline.import_gpu_outputs --stage music path/to/music-candidates`, then `make stage S=music` to see the imported files. After listening, run `python -m pipeline.music --select 2` to choose candidate 2. Changing the music brief or the chosen candidate's seed requires a matching import and a new selection.

### Narration voice

Gemini TTS, English. Style instruction: *Read warmly and playfully, like a friend telling a story. Light comic timing on the jokes, slower and softer on the last two lines.* One file per shot, so one line can be re-taken without redoing the rest.

---

## Consent, labelling and licences

- I am the real person depicted and voiced. My consent is recorded in `ETHICS.md` before anything is generated.
- My mother appears in shots 4 and 9. Until her consent is recorded in `ETHICS.md`, draw her from behind, as a silhouette, or show only her hands.
- Describe styles by their qualities, never by naming a living artist.
- Do not send private family details to free endpoints that may train on inputs.
- End card says "Made with AI". Keep SynthID and C2PA metadata intact where present. Post with the platform's AI label on.
- Record every model and output licence in `ETHICS.md`. Starting points: Wan 2.2 Apache 2.0, ACE-Step 1.5 MIT with commercially usable outputs, FLUX.1 schnell Apache 2.0, FLUX.2 klein 4B Apache 2.0 (the 9B is non-commercial). Verify, do not assume.

---

## Optional: showcase site

After the film is done, build `site/` from my Stitch designs, using Next.js, TypeScript and Tailwind, exported statically. It reads `storyboard.json` and `runs.jsonl` (copied to `site/public/data/` at build time) and shows: the film in both ratios, the storyboard timeline with the reason for each shot, the pipeline stages with latency and cache status, an experiments and costs table, audience feedback, and an ethics and credits section. It must meet WCAG AA, with captions on by default. Do not start this until `make film` works from a clean clone.

---

## Optional: Heritage Studio (web app for non-developers)

A web app where someone who does not code shares a story and photos and gets a short film back. This is ceiling work ("a tool for your family"). It is a thin layer over the same pipeline, not a second system. **Do not start it until `make film` works from a clean clone.**

### Principles

- One pipeline, two entry points: the CLI (`make film`) and the web app. The web backend calls the same stage scripts, so caching, retries and `runs.jsonl` logging come for free.
- Every stage must accept a working directory (for example `--workdir jobs/<job_id>`), defaulting to the repo root. The CLI keeps working unchanged.
- The web path never runs Wan 2.2. Studio films use FLUX keyframes plus the FFmpeg Ken Burns fallback. A Wan clip can be imported later by hand (`import_gpu_outputs.py`) as an optional upgrade.
- Local first. A public demo is optional and only with rate limits (see Safety).

### Stack

- Frontend: Next.js, TypeScript, Tailwind, built from my Stitch designs, in `studio/web/`.
- Backend: FastAPI (Python, so it can import `pipeline/` directly), in `studio/api/`.
- Jobs: a folder per job, no database. Status is a small `status.json` file polled by the frontend every 2-3 seconds. No websockets.

### Job folder

```
jobs/<job_id>/
  input.json          story text, language, created_at
  consent.json        consent checkbox, timestamp, wording shown to the user
  uploads/            user photos (validated, EXIF stripped)
  storyboard.json     same schema as the main storyboard
  status.json         state, current stage, per-shot progress, error
  outputs/            narration, keyframes, shots, music, final MP4s (same layout as the main repo)
  runs.jsonl          model calls for this job
```

### Job states

`created -> storyboard_drafted -> storyboard_approved -> radio_ready -> generating -> done` (or `failed`, with the stage and error message). Generation is blocked unless `consent.json` exists and is valid.

### API

| Method and path | What it does |
|---|---|
| `POST /api/jobs` | Create a job from story text, language, consent flag and photo uploads. Returns `job_id`. |
| `POST /api/jobs/{id}/storyboard/draft` | Gemini drafts 6-10 shots, each with a `reason`, from the story. Validates against the schema. |
| `GET /api/jobs/{id}/storyboard` | Return the current storyboard. |
| `PUT /api/jobs/{id}/storyboard` | Save the user's edits (narration, prompts). Validate before saving. |
| `POST /api/jobs/{id}/radio` | Run narration and assemble the radio cut. |
| `POST /api/jobs/{id}/generate` | Run keyframes, shots (Ken Burns), music and assembly. Only changed shots regenerate. |
| `GET /api/jobs/{id}/status` | Return `status.json`. |
| `GET /api/jobs/{id}/download/{vertical\|horizontal\|srt}` | Download the finished files. |

### Screens (match the Stitch design)

1. Welcome.
2. Story input: text area, photo drop zone, language picker (English, Amharic), required consent checkbox in plain language.
3. Storyboard review: shot cards, each with a thumbnail placeholder, an editable narration line and a "why this shot" caption.
4. Radio cut preview: audio player and a feedback prompt ("What made you laugh? What confused you?"). Feedback is stored in `jobs/<id>/feedback.json`.
5. Progress: step tracker (Narration, Pictures, Music, Edit) with status chips and a "Made with AI" note.
6. Result: 9:16 and 16:9 player toggle, download buttons, share button, visible AI label.

### Safety rules (non-negotiable)

- **Consent gate, enforced on the server:** no generation without a valid `consent.json`. The checkbox text says everyone shown or voiced has agreed.
- **Labelling:** the "Made with AI" end card is always added and cannot be turned off in the UI or the API.
- **Photos:** accept only jpg, png and webp, with a size limit (for example 8 MB each, 10 files). Strip EXIF. Treat photos of real people as likeness: use them only as reference input, never send them to an endpoint without showing the user the privacy note, and never animate a raw photo of a person.
- **Privacy note shown at upload:** free endpoints may use inputs for training, so avoid private details.
- **API keys stay server-side only.** Never expose them to the browser.
- **Rate limits:** per-IP limit on job creation and a global daily cap on model calls, so a public demo cannot burn the free quota. If the cap is hit, show a friendly message.
- **Cleanup:** delete job folders (uploads included) after a set time, for example 24 hours, unless the user downloads and keeps them.

### Hosting

Run locally for the demo. Optionally deploy as a Hugging Face Docker Space (free CPU, FFmpeg installed in the image) with secrets set in the Space settings and the rate limits above switched on.

Start the local API from the repository root. Install its dependencies in the same virtual environment as the pipeline, then run Uvicorn on the loopback interface.

```powershell
.\.venv\Scripts\python.exe -m pip install -r studio/api/requirements.txt
.\.venv\Scripts\python.exe -m uvicorn studio.api.main:app --host 127.0.0.1 --port 8000
```

Interactive API docs are at `http://127.0.0.1:8000/docs`. Fetch `GET /api/config` for the current consent wording, privacy notice, and photo limits. Create jobs with multipart fields `story`, `language` (`en` or `am`), `consent`, `privacy_acknowledged` when photos are attached, and repeated `photos` uploads. Storyboard drafting, radio generation, and film generation return HTTP 202. Poll the status endpoint to track progress. Submit `PUT /api/jobs/{id}/storyboard?approve=true` to approve the reviewed storyboard. GET the radio endpoint to play the preview and POST feedback as `{"laughed":"...","confused":"..."}`.

Studio uses illustrated FLUX keyframes, Ken Burns motion, and the placeholder score until a matching ACE-Step track is imported and selected for that job. The API is configured for a single local server process. Expired job folders are removed after 24 hours of inactivity, and downloaded copies stay on the user's device.

For backend tests, install `studio/api/requirements-dev.txt` and run `python -m unittest discover -s studio/api/tests -v` in the project environment.

### Evidence for the report

I will run one experiment: 3 non-developers try to make a film without my help. I write the result in `EXPERIMENTS.md` myself. Make sure the app records stage timings and failures per job so I have real data. Do not write the results for me.

---

## Deadline

Both submissions are due **Thursday 26 November 2026, 23:59 East Africa Time**. Priorities, in order:

1. `make film` works from a clean clone and always produces a film (Ken Burns fallback).
2. `runs.jsonl`, `DESIGN.md`, `EXPERIMENTS.md` and `FAILURES.md` are honest and complete.
3. Wan 2.2 clips for as many shots as the Kaggle quota allows.
4. Heritage Studio (web app), only after 1-3 are solid.
5. The showcase site, last.

---

## Instructions for the coding agent

You write the code. I design and review. Work in this order and stop after each step for my review:

1. Create the repo skeleton, `Makefile`, `config.yaml`, `.gitignore` (include `.env`) and `.env.example`.
2. Write `schema/storyboard.schema.json` and a validator. Then draft `storyboard.json` from the table above and validate it.
3. Write shared utilities: input hashing, cache index, retry with backoff, and the `runs.jsonl` logger. Add small unit tests.
4. `make smoke`: one call each to Gemini text, Gemini TTS and Cloudflare FLUX, logged to `runs.jsonl`.
5. `narration` stage and `make radio` (narration over placeholder music on black).
6. `keyframes` stage, including the character reference sheet step.
7. `shots` stage with the Ken Burns fallback, the Kaggle notebook scripts and `import_gpu_outputs.py`.
8. `music` stage and import.
9. `assemble` stage: cut, ducking, subtitles, loudnorm, end card, both aspect ratios.
10. Draft `ARCHITECTURE.md` and `COSTS.md` from the real logs, never from guesses.

**Do not start steps 11-14 until step 9 works from a clean clone and I say so.**

11. Refactor every stage to accept `--workdir` (default: repo root) without breaking `make film`. Add a test that runs a stage against a temporary job folder.
12. Build `studio/api/` (FastAPI): job creation, consent gate, photo validation and EXIF stripping, the endpoints in the Studio section, `status.json` updates, rate limits and job cleanup. Add tests for the consent gate and for schema validation of edited storyboards.
13. Build `studio/web/` (Next.js, TypeScript, Tailwind) from my Stitch designs: the six screens, polling the status endpoint, accessible and mobile-first.
14. Add `make studio` (run API and web locally) and a short Studio section in `ARCHITECTURE.md` explaining that it reuses the same stages.

Rules:

- Never hardcode secrets, model names or prompts in code. Prompts and seeds live in `storyboard.json`.
- Never invent measurements, costs or experiment results. If a number is missing, leave a TODO.
- Do not touch `DESIGN.md`, `EXPERIMENTS.md`, `FAILURES.md` or `ETHICS.md` content beyond templates. I write those from real events. You may add a template and append a line to `FAILURES.md` when I tell you something broke.
- Keep each stage runnable on its own and re-runnable without repeating finished work.
- Commit small and often, with clear messages.
- If a model, endpoint or free-tier limit differs from what this README says, tell me and propose the replacement. Do not silently substitute.
- Studio code must reuse `pipeline/`. Do not duplicate stage logic in the web backend.
- Enforce the consent gate and the AI end card on the server, never only in the UI.
- Never expose API keys to the browser, and never log uploaded photos' contents or private story text to `runs.jsonl` (log hashes and sizes only).
