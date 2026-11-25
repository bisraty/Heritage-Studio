"use client";

import { useState } from "react";
import {
  AudioLines, Captions, Check, CircleCheck, Clapperboard, Download, Film, Frame, Images, MessageSquare,
  Monitor, Music2, Scissors, Share2, Smartphone, Sparkles, Timer,
} from "lucide-react";
import { API, jobUrl, type JobStatus, type Orientation, type Storyboard } from "../api";
import { FilmPlayer } from "./film-player";
import { mediaTime } from "./media-time";
import { RadioPlayer } from "./radio-player";

const phases = [
  { key: "narration", label: "Narration Synthesis", description: "Prepare the voice clips for your storyboard.", Icon: AudioLines },
  { key: "pictures", label: "Illustrations & Motion", description: "Generate each illustration and add gentle camera motion.", Icon: Images },
  { key: "music", label: "Score & Acoustic Layers", description: "Prepare the background score to sit beneath the narration.", Icon: Music2 },
  { key: "edit", label: "Final Assembly", description: "Mix the soundtrack, add captions, and export both film formats.", Icon: Scissors },
] as const;

const phaseText = { pending: "Queued", running: "In progress", done: "Completed", failed: "Needs attention" };

type Feedback = { laughed: string; confused: string };
const quickNotes: { text: string; field: keyof Feedback }[] = [
  { text: "The story made me laugh", field: "laughed" },
  { text: "The pacing felt too fast", field: "confused" },
  { text: "Add a pause before the ending", field: "confused" },
];

function pictureIds(status: JobStatus | null, storyboard: Storyboard | null) {
  const ids = storyboard?.shots.map((shot) => shot.id) ?? Object.keys(status?.shots ?? {}).map(Number);
  return ids.filter((id) => status?.shots[String(id)]?.pictures === "done");
}

function frameUrl(job: string, id: number) {
  return API + jobUrl(job, `frames/${id}`);
}

export function RadioHeading({ job, ready }: { job: string | null; ready: boolean }) {
  return <div className="stage-heading listening-heading">
    <div>
      <h1>Radio Cut Preview</h1>
      <p>Listen to the voiceover, pacing, and score before final film assembly.</p>
    </div>
    {job && ready && <a className="button console-button" href={API + jobUrl(job, "radio/audio")}>
      <Download size={17} /> Export Audio (.WAV)
    </a>}
  </div>;
}

export function RadioReview({
  job, storyboard, feedback, setFeedback, saved, busy, save, edit, generate,
}: {
  job: string;
  storyboard: Storyboard | null;
  feedback: Feedback;
  setFeedback: (value: Feedback) => void;
  saved: boolean;
  busy: boolean;
  save: () => void;
  edit: () => void;
  generate: () => void;
}) {
  function toggleNote(field: keyof Feedback, text: string) {
    const notes = feedback[field].split("\n").filter(Boolean);
    const next = notes.includes(text) ? notes.filter((note) => note !== text) : [...notes, text];
    setFeedback({ ...feedback, [field]: next.join("\n") });
  }

  return <>
    <div className="screening-grid radio-review">
      <RadioPlayer job={job} storyboard={storyboard} />
      <section className="panel listening-notes" aria-labelledby="feedback-heading">
        <div className="console-label"><MessageSquare size={14} /> Storyteller listening check</div>
        <h2 id="feedback-heading">Did this make you laugh? What confused you?</h2>
        <p>Save a quick reaction or leave notes on the pacing and narration.</p>
        <div className="reaction-list" role="group" aria-label="Quick reactions">
          {quickNotes.map(({ text, field }) => (
            <button type="button" key={text} aria-pressed={feedback[field].split("\n").includes(text)}
              disabled={busy} onClick={() => toggleNote(field, text)}>
              <span>{text}</span><CircleCheck size={16} aria-hidden="true" />
            </button>
          ))}
        </div>
        <label htmlFor="laughed">What made you laugh?</label>
        <textarea id="laughed" rows={2} maxLength={2000} placeholder="A line or moment you enjoyed" value={feedback.laughed}
          onChange={(event) => setFeedback({ ...feedback, laughed: event.target.value })} />
        <label htmlFor="confused">What confused you?</label>
        <textarea id="confused" rows={2} maxLength={2000} placeholder="A line, pronunciation, or pacing note" value={feedback.confused}
          onChange={(event) => setFeedback({ ...feedback, confused: event.target.value })} />
        <button type="button" className="button console-button" disabled={busy} onClick={save}>Save Feedback</button>
        {saved && <p role="status" className="saved-note"><Check size={15} /> Feedback saved.</p>}
      </section>
    </div>
    <div className="panel review-actions">
      <button type="button" className="button console-button" onClick={edit}>Edit Storyboard</button>
      <div className="next-stage">
        <span className="production-icon"><Film size={18} /></span>
        <div><strong>Ready for final assembly</strong><p>Prepare the illustrations and render both formats.</p></div>
      </div>
      <button type="button" className="button primary" disabled={busy} onClick={generate}><Clapperboard size={18} /> Generate Film</button>
    </div>
  </>;
}

export function ProcessingHeading({ status }: { status: JobStatus | null }) {
  const completed = phases.filter(({ key }) => status?.stages[key] === "done").length;
  return <div className="stage-heading processing-heading">
    <div>
      <h1>Crafting Your Heritage Film</h1>
      <p>Watch the four production stages as your film comes together.</p>
    </div>
    <div className="render-counter" aria-label={`${completed} of four production stages complete`}>
      <span><small>Render progress</small><strong>{completed * 25}% complete</strong></span>
      <Timer size={22} aria-hidden="true" />
    </div>
  </div>;
}

function FramePreview({ job, ids }: { job: string | null; ids: number[] }) {
  const [selected, select] = useState<number | null>(null);
  const [unavailable, setUnavailable] = useState<number[]>([]);
  const available = ids.filter((id) => !unavailable.includes(id));
  const active = selected !== null && available.includes(selected) ? selected : available.at(-1);
  return <section className="panel frame-preview" aria-labelledby="frame-preview-heading">
    <div className="frame-preview-header">
      <h2 id="frame-preview-heading"><Frame size={16} /> Frame Preview</h2>
      {active !== undefined && <span>Shot {active}</span>}
    </div>
    <div className="frame-preview-picture">
      {job && active !== undefined
        ? <img src={frameUrl(job, active)} alt={`Generated illustration for shot ${active}`}
          onError={() => setUnavailable((current) => [...current, active])} />
        : <div className="frame-preview-empty"><Frame size={29} /><p>Illustrations appear here as they finish.</p></div>}
    </div>
    {job && available.length > 0 && <div className="frame-strip" aria-label="Generated illustrations">
      {available.map((id) => <button key={id} type="button" aria-label={`Preview shot ${id}`} aria-pressed={id === active} onClick={() => select(id)}>
        <img src={frameUrl(job, id)} alt="" loading="lazy" onError={() => setUnavailable((current) => [...current, id])} />
      </button>)}
    </div>}
  </section>;
}

export function ProcessingReview({
  job, storyboard, status, busy, retry, openFilm,
}: {
  job: string | null;
  storyboard: Storyboard | null;
  status: JobStatus | null;
  busy: boolean;
  retry: () => void;
  openFilm: () => void;
}) {
  const completed = phases.filter(({ key }) => status?.stages[key] === "done").length;
  const ids = pictureIds(status, storyboard);
  return <section aria-label="Film production">
    <div className="render-overview">
      <progress aria-label="Film progress" value={completed} max={phases.length} />
      <div className="progress-summary"><strong>Film progress</strong><span>{completed} of {phases.length} stages complete</span></div>
    </div>
    <div className="screening-grid production-grid">
      <section aria-labelledby="production-title">
        <div className="production-title"><Clapperboard size={19} /><h2 id="production-title">Production Pipeline</h2></div>
        <ul className="phase-list">
          {phases.map(({ key, label, description, Icon }) => {
            const state = status?.stages[key] ?? "pending";
            const count = Object.values(status?.shots ?? {}).filter((shot) => shot[key] === "done").length;
            const total = storyboard?.shots.length;
            return <li key={key} className={`panel phase-card ${state}`}>
              <span className="production-icon"><Icon size={19} /></span>
              <div className="phase-card-body">
                <div className="phase-card-heading"><strong>{label}</strong><span className={`phase-status ${state}`}>{phaseText[state]}</span></div>
                <p>{description}</p>
                {state !== "pending" && total && (key === "narration" || key === "pictures") && (
                  <div className="phase-measure"><span>{count} of {total} {key === "narration" ? "voice clips" : "illustrations"}</span>
                    <progress aria-label={`${label} progress`} value={count} max={total} /></div>
                )}
              </div>
              {state === "done" && <CircleCheck className="phase-check" size={17} aria-hidden="true" />}
            </li>;
          })}
        </ul>
      </section>
      <div className="screening-stack">
        <FramePreview job={job} ids={ids} />
        <section className="panel production-note">
          <span className="production-icon"><Sparkles size={18} /></span>
          <div><h2>Made with AI</h2><p>The finished film includes a “Made with AI” end card.</p></div>
        </section>
      </div>
    </div>
    {!busy && status?.state !== "done" && <div className="actions footer-actions"><button className="button primary" onClick={retry}>Retry Film Generation</button></div>}
    {status?.downloads && <div className="actions footer-actions"><button className="button primary" onClick={openFilm}>Open Film</button></div>}
  </section>;
}

export function FinalReview({
  job, storyboard, status, orientation, setOrientation, pending, share,
}: {
  job: string;
  storyboard: Storyboard | null;
  status: JobStatus;
  orientation: Orientation;
  setOrientation: (value: Orientation) => void;
  pending: boolean;
  share: () => void;
}) {
  const [duration, setDuration] = useState(0);
  const ids = pictureIds(status, storyboard);
  return <section className="final-screen">
    <div className="stage-heading final-heading">
      <h1>Your Heritage Film Is Ready</h1>
      {storyboard && <p>{storyboard.title}</p>}
    </div>
    <div className="format-switch" role="group" aria-label="Video aspect ratio">
      <button type="button" aria-pressed={orientation === "horizontal"} onClick={() => setOrientation("horizontal")}><Monitor size={17} /> Landscape 16:9</button>
      <button type="button" aria-pressed={orientation === "vertical"} onClick={() => setOrientation("vertical")}><Smartphone size={17} /> Portrait 9:16</button>
    </div>
    <FilmPlayer key={orientation} orientation={orientation} onDuration={setDuration}
      src={API + jobUrl(job, `preview/${orientation}`)}
      poster={ids.length > 0 ? frameUrl(job, ids[0]) : undefined} />
    <div className="film-label"><span className="ai-label"><Sparkles size={14} /> {status.ai_label ?? "Made with AI"}</span></div>
    <div className="panel export-tray">
      <div className="export-formats">
        <a className="button primary" href={API + jobUrl(job, `download/${orientation}`)}><Download size={19} /> Download Film</a>
        <a className="button console-button" href={API + jobUrl(job, "download/vertical")}><Smartphone size={16} /> 9:16 MP4</a>
        <a className="button console-button" href={API + jobUrl(job, "download/horizontal")}><Monitor size={16} /> 16:9 MP4</a>
      </div>
      <div className="export-tools">
        <button type="button" className="button console-button" onClick={share} disabled={pending}><Share2 size={18} /> Share Preview</button>
        <a className="button console-button" href={API + jobUrl(job, "download/srt")}><Captions size={17} /> Download Captions</a>
      </div>
    </div>
    {(storyboard || duration > 0) && <section className="panel screening-record" aria-labelledby="record-heading">
      <h2 id="record-heading"><Film size={19} /> Film Details</h2>
      <div className="record-facts">
        {duration > 0 && <div><span>Runtime</span><strong>{mediaTime(duration)}</strong></div>}
        {storyboard && <div><span>Storyboard</span><strong>{storyboard.shots.length} shots</strong></div>}
        <div><span>Captions</span><strong>{storyboard?.language === "am" ? "Amharic" : "English"}</strong></div>
        <div><span>Score</span><strong>{status.score === "imported" ? "Imported track" : "Temporary mix"}</strong></div>
      </div>
    </section>}
  </section>;
}
