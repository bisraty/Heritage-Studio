"use client";

import { useEffect, useRef, useState } from "react";
import type { FormEvent, ReactNode } from "react";
import {
  AudioLines, Check, Clapperboard, Download, Film, Frame, Images, ListVideo,
  LoaderCircle, LockKeyhole, Music2, Scissors, Share2, Upload, X,
} from "lucide-react";
import {
  API, ApiError, jobUrl, jsonBody, request,
  type Action, type JobStatus, type Orientation, type Screen, type Storyboard, type StudioConfig,
} from "./api";

const screens: [Screen, string][] = [
  ["welcome", "Welcome"], ["story", "Story Input"], ["storyboard", "Storyboard"],
  ["radio", "Radio Cut"], ["progress", "Processing"], ["film", "Final Film"],
];

const phaseDetails = [
  { key: "narration", label: "Narration", Icon: AudioLines },
  { key: "pictures", label: "Pictures", Icon: Images },
  { key: "music", label: "Music", Icon: Music2 },
  { key: "edit", label: "Edit", Icon: Scissors },
] as const;

const actionTarget: Record<Action, [Screen, string]> = {
  draft: ["storyboard", "storyboard/draft"],
  radio: ["radio", "radio"],
  generate: ["progress", "generate"],
};

function heading(title: string, description?: string) {
  return <div className="screen-heading"><h1>{title}</h1>{description && <p>{description}</p>}</div>;
}

function Loading({ children }: { children: ReactNode }) {
  return <div className="loading-panel" role="status"><LoaderCircle className="spin" aria-hidden="true" size={22} />{children}</div>;
}

function Photo({ file, remove }: { file: File; remove: () => void }) {
  const [url, setUrl] = useState("");
  useEffect(() => {
    const objectUrl = URL.createObjectURL(file);
    setUrl(objectUrl);
    return () => URL.revokeObjectURL(objectUrl);
  }, [file]);
  return (
    <li className="photo">
      {url && <img src={url} alt="" />}
      <span title={file.name}>{file.name}</span>
      <button className="icon-button" type="button" aria-label={`Remove ${file.name}`} onClick={remove}><X size={15} /></button>
    </li>
  );
}

function Welcome({ start, resume }: { start: () => void; resume: boolean }) {
  const features = [
    { image: "voice", Icon: AudioLines, title: "Share your memory", description: "Start with a story in English or Amharic." },
    { image: "photos", Icon: Images, title: "Bring your photos", description: "Use family photographs as references for the illustrations." },
    { image: "edit", Icon: Clapperboard, title: "Review your film", description: "Edit the storyboard and listen to the narration before rendering." },
  ];
  return <>
    <section className="hero">
      <div className="hero-content">
        <h1>Turn treasured family memories into <em>timeless short films.</em></h1>
        <p>Tell your story, add your photos, and make a film your family can keep.</p>
        <div className="actions justify-center">
          <button className="button primary" onClick={start}><Film size={18} /> {resume ? "Resume Your Story" : "Start Your Story"}</button>
          <a className="button secondary" href="#how-it-works">How It Works</a>
        </div>
      </div>
    </section>
    <section className="feature-grid" id="how-it-works" aria-label="How it works">
      {features.map(({ image, Icon, title, description }) => (
        <article className="feature panel" key={image}>
          <div className="feature-image" style={{ backgroundImage: `url('/stitch/${image}.webp')` }} />
          <div className="feature-body"><Icon className="gold" size={21} /><h2>{title}</h2><p>{description}</p></div>
        </article>
      ))}
    </section>
  </>;
}

function restoredScreen(status: JobStatus): Screen {
  if (status.state === "done") return "film";
  if (status.busy || status.state === "failed") return actionTarget[status.action ?? "draft"][0];
  if (status.radio || status.approved) return "radio";
  return "storyboard";
}

const storageKey = "heritage-studio-current-job";

export default function Studio() {
  const [screen, setScreen] = useState<Screen>("welcome");
  const [job, setJob] = useState<string | null>(null);
  const [status, setStatus] = useState<JobStatus | null>(null);
  const [config, setConfig] = useState<StudioConfig | null>(null);
  const [storyboard, setStoryboard] = useState<Storyboard | null>(null);
  const [story, setStory] = useState("");
  const [language, setLanguage] = useState<"en" | "am">("en");
  const [photos, setPhotos] = useState<File[]>([]);
  const [consent, setConsent] = useState(false);
  const [privacy, setPrivacy] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [connection, setConnection] = useState("");
  const [feedback, setFeedback] = useState({ laughed: "", confused: "" });
  const [feedbackSaved, setFeedbackSaved] = useState(false);
  const [orientation, setOrientation] = useState<Orientation>("vertical");
  const [notice, setNotice] = useState("");
  const fileInput = useRef<HTMLInputElement>(null);
  const restore = useRef(false);
  const main = useRef<HTMLElement>(null);

  useEffect(() => {
    const saved = sessionStorage.getItem(storageKey);
    if (saved) {
      restore.current = true;
      setJob(saved);
    }
  }, []);

  useEffect(() => {
    if (screen !== "welcome") {
      main.current?.focus({ preventScroll: true });
      window.scrollTo(0, 0);
    }
  }, [screen]);

  useEffect(() => {
    if (screen !== "story" || config) return;
    const controller = new AbortController();
    request<StudioConfig>("/api/config", { signal: controller.signal })
      .then(setConfig).catch((cause) => { if (!controller.signal.aborted) setError(cause.message); });
    return () => controller.abort();
  }, [screen, config]);

  function acceptStatus(next: JobStatus) {
    setStatus((current) => current && current.updated_at > next.updated_at ? current : next);
    if (restore.current) {
      restore.current = false;
      setScreen(restoredScreen(next));
    } else if (next.state === "done") {
      setScreen((current) => current === "progress" ? "film" : current);
    }
  }

  useEffect(() => {
    if (!job) return;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      try {
        const next = await request<JobStatus>(jobUrl(job!, "status"), { signal: controller.signal });
        if (controller.signal.aborted) return;
        setConnection("");
        acceptStatus(next);
      } catch (cause) {
        if (controller.signal.aborted) return;
        if (cause instanceof ApiError && cause.status === 404) {
          sessionStorage.removeItem(storageKey);
          setJob(null);
          setStatus(null);
          setStoryboard(null);
          setScreen("story");
          setError("This job has expired. Start a new story to continue.");
          return;
        }
        setConnection(cause instanceof Error ? cause.message : "Waiting for the local API.");
      }
      timer = setTimeout(poll, 2500);
    }
    void poll();
    return () => { controller.abort(); clearTimeout(timer); };
  }, [job]);

  const needsStoryboard = Boolean(status?.approved || status?.radio || status?.state === "storyboard_drafted");
  useEffect(() => {
    if (!job || !needsStoryboard || storyboard) return;
    const controller = new AbortController();
    request<Storyboard>(jobUrl(job, "storyboard"), { signal: controller.signal })
      .then(setStoryboard).catch((cause) => { if (!controller.signal.aborted) setError(cause.message); });
    return () => controller.abort();
  }, [job, needsStoryboard, storyboard]);

  async function perform(action: () => Promise<void>) {
    setPending(true);
    setError("");
    setNotice("");
    try { await action(); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Something went wrong. Try again."); }
    finally { setPending(false); }
  }

  async function queue(action: Action, identifier: string) {
    const [target, endpoint] = actionTarget[action];
    setScreen(target);
    await request(jobUrl(identifier, endpoint), { method: "POST" });
    acceptStatus(await request<JobStatus>(jobUrl(identifier, "status")));
  }

  function addPhotos(newFiles: FileList | null) {
    if (!newFiles || !config) return;
    const next = Array.from(newFiles);
    if (photos.length + next.length > config.max_photos) {
      setError(`Add up to ${config.max_photos} photos.`);
      return;
    }
    if (next.some((file) => !/\.(jpe?g|png|webp)$/i.test(file.name) || file.size > config.max_photo_bytes)) {
      setError(`Choose JPG, PNG, or WebP files up to ${Math.round(config.max_photo_bytes / 1048576)} MB each.`);
      return;
    }
    setError("");
    setPhotos((current) => [...current, ...next]);
  }

  function create(event: FormEvent) {
    event.preventDefault();
    if (!config || !consent || (photos.length > 0 && !privacy)) return;
    void perform(async () => {
      const data = new FormData();
      data.set("story", story.trim());
      data.set("language", language);
      data.set("consent", String(consent));
      data.set("privacy_acknowledged", String(privacy));
      photos.forEach((file) => data.append("photos", file));
      const result = await request<{ job_id: string }>("/api/jobs", { method: "POST", body: data });
      sessionStorage.setItem(storageKey, result.job_id);
      setJob(result.job_id);
      setPhotos([]);
      await queue("draft", result.job_id);
    });
  }

  function approve() {
    if (!job || !storyboard) return;
    void perform(async () => {
      if (dirty || !status?.approved) {
        await request(jobUrl(job, "storyboard?approve=true"), jsonBody(storyboard, "PUT"));
        setDirty(false);
      } else if (status.radio) {
        setScreen("radio");
        return;
      }
      await queue("radio", job);
    });
  }

  function changeShot(index: number, field: "narration" | "image_prompt", value: string) {
    setDirty(true);
    setStoryboard((current) => current && ({
      ...current,
      shots: current.shots.map((shot, position) => position === index ? { ...shot, [field]: value } : shot),
    }));
  }

  function retry(action: Action) {
    if (job) void perform(() => queue(action, job));
  }

  function saveFeedback(thenGenerate = false) {
    if (!job) return;
    void perform(async () => {
      if (!thenGenerate || feedback.laughed.trim() || feedback.confused.trim()) {
        await request(jobUrl(job, "feedback"), jsonBody(feedback, "POST"));
        setFeedbackSaved(true);
      }
      if (thenGenerate) await queue("generate", job);
    });
  }

  function reset() {
    sessionStorage.removeItem(storageKey);
    restore.current = false;
    setJob(null);
    setStatus(null);
    setStoryboard(null);
    setStory("");
    setPhotos([]);
    setConsent(false);
    setPrivacy(false);
    setDirty(false);
    setError("");
    setConnection("");
    setNotice("");
    setFeedback({ laughed: "", confused: "" });
    setFeedbackSaved(false);
    setOrientation("vertical");
    setScreen("story");
  }

  function share() {
    if (!job) return;
    void perform(async () => {
      const url = API + jobUrl(job, `preview/${orientation}`);
      if (navigator.share) {
        try { await navigator.share({ title: storyboard?.title ?? "Heritage Film", url }); }
        catch (cause) { if (!(cause instanceof DOMException && cause.name === "AbortError")) throw cause; }
      } else {
        await navigator.clipboard.writeText(url);
        setNotice("Local preview link copied.");
      }
    });
  }

  const busy = pending || Boolean(status?.busy);
  const completed = phaseDetails.filter(({ key }) => status?.stages[key] === "done").length;
  const allowed: Record<Screen, boolean> = {
    welcome: true, story: !job, storyboard: Boolean(job), radio: Boolean(status?.approved),
    progress: status?.action === "generate" || status?.state === "done", film: Boolean(status?.downloads),
  };
  const phaseText: Record<string, string> = { pending: "Waiting", running: "In progress", done: "Complete", failed: "Needs attention" };

  return <>
    <a href="#studio-main" className="skip-link">Skip to content</a>
    <header className="site-header">
      <div className="shell brand-bar">
        <button className="brand" onClick={() => setScreen("welcome")} aria-label="Heritage Studio home">
          <span className="brand-icon"><Film size={22} aria-hidden="true" /></span>
          <span>Heritage Studio</span>
        </button>
        {job ? <button className="button ghost compact" disabled={busy} onClick={reset}>New Story</button> :
          <span className="local-mark"><LockKeyhole size={14} /> Local Studio</span>}
      </div>
      <nav className="shell steps" aria-label="Film production steps">
        {screens.map(([key, label]) => <button key={key} aria-current={screen === key ? "step" : undefined}
          className={screen === key ? "step active" : "step"} disabled={!allowed[key] && screen !== key}
          onClick={() => { setError(""); setScreen(key); }}>{label}</button>)}
      </nav>
    </header>

    <main className="shell main-content" id="studio-main" tabIndex={-1} ref={main}>
      {connection && <p className="banner" role="status">{connection}</p>}
      {error && <p className="banner error" role="alert">{error}</p>}
      {status?.error && !error && status.state === "failed" && <p className="banner error" role="alert">{status.error}</p>}
      {notice && <p className="banner" role="status">{notice}</p>}

      {screen === "welcome" && <Welcome resume={Boolean(job)} start={() => setScreen(status ? restoredScreen(status) : job ? "storyboard" : "story")} />}

      {screen === "story" && <section>
        {heading("Share Your Story", "Start with a memory, a family story, or a script. You can add photos to guide the illustrations.")}
        <form onSubmit={create}>
          <div className="story-grid">
            <section className="panel field-panel">
              <div className="section-title"><AudioLines size={19} /><h2>Written Memory</h2></div>
              <label htmlFor="story-text">Your story</label>
              <textarea id="story-text" name="story" required maxLength={12000} rows={10}
                placeholder="Where does your story begin?" value={story} onChange={(event) => setStory(event.target.value)} />
              <div className="field-footer">
                <label className="language">Narration language
                  <select value={language} onChange={(event) => setLanguage(event.target.value as "en" | "am")}>
                    <option value="en">English</option><option value="am">አማርኛ · Amharic</option>
                  </select>
                </label>
                <span className="muted">{story.length.toLocaleString()} / 12,000</span>
              </div>
            </section>
            <section className="panel field-panel">
              <div className="section-title"><Images size={19} /><h2>Cherished Photographs</h2></div>
              <button type="button" className="dropzone" disabled={!config || busy}
                onClick={() => fileInput.current?.click()}
                onDragOver={(event) => event.preventDefault()}
                onDrop={(event) => { event.preventDefault(); if (!busy) addPhotos(event.dataTransfer.files); }}>
                <Upload aria-hidden="true" size={23} />
                <strong>Choose or drop photographs</strong>
                <span>JPG, PNG, or WebP · {config?.max_photos ?? 10} photos maximum</span>
              </button>
              <input ref={fileInput} type="file" hidden multiple accept="image/jpeg,image/png,image/webp"
                aria-label="Choose photographs" onChange={(event) => { addPhotos(event.target.files); event.target.value = ""; }} />
              {photos.length > 0 && <ul className="photo-grid">{photos.map((file, index) => (
                <Photo key={`${index}-${file.name}`} file={file} remove={() => setPhotos((current) => current.filter((_, i) => i !== index))} />
              ))}</ul>}
              <p className="privacy">{config?.privacy_note ?? "Loading the Studio privacy notice."}</p>
              {photos.length > 0 && <label className="check-row">
                <input type="checkbox" required checked={privacy} onChange={(event) => setPrivacy(event.target.checked)} />
                <span>I’ve read the photo privacy notice.</span>
              </label>}
            </section>
          </div>
          <div className="panel consent-block">
            <LockKeyhole size={19} className="gold" />
            <label className="check-row">
              <input type="checkbox" required checked={consent} onChange={(event) => setConsent(event.target.checked)} />
              <span>{config?.consent ?? "Everyone shown or voiced in this film has agreed to it."}</span>
            </label>
          </div>
          <div className="actions footer-actions">
            {!config && error && <button type="button" className="button secondary" onClick={() => void perform(async () => setConfig(await request<StudioConfig>("/api/config")))}>Retry API Connection</button>}
            <button className="button primary" disabled={busy || !config || !story.trim() || !consent || (photos.length > 0 && !privacy)}>
              <ListVideo size={18} /> {pending ? "Preparing…" : "Draft Storyboard"}
            </button>
          </div>
        </form>
      </section>}

      {screen === "storyboard" && <section>
        {heading("Storyboard Review", "Review each scene, edit the narration, and see why the scene is in your film.")}
        {status?.draft_source === "local" && status.state === "storyboard_drafted" &&
          <p className="banner" role="status">Gemini was busy. This local draft uses excerpts from your story. Review the narration before approving.</p>}
        {busy && !storyboard && <Loading>Drafting your storyboard…</Loading>}
        {!busy && !storyboard && <button className="button primary" onClick={() => retry("draft")}>Draft Storyboard</button>}
        {storyboard && <>
          <h2 className="project-title">{storyboard.title}</h2>
          <div className="shot-grid">{storyboard.shots.map((shot, index) => (
            <article className="panel shot" key={shot.id}>
              <div className="shot-preview"><Frame size={28} aria-hidden="true" /><span>Shot {shot.id} · {shot.shot_size}</span></div>
              <div className="shot-body">
                <label htmlFor={`narration-${shot.id}`}>Narration</label>
                <textarea id={`narration-${shot.id}`} rows={3} value={shot.narration} disabled={busy}
                  onChange={(event) => changeShot(index, "narration", event.target.value)} />
                <p><strong>Why this shot</strong> {shot.reason}</p>
                <details>
                  <summary>Visual direction</summary>
                  <label className="sr-only" htmlFor={`prompt-${shot.id}`}>Shot {shot.id} image prompt</label>
                  <textarea id={`prompt-${shot.id}`} rows={3} value={shot.image_prompt} disabled={busy}
                    onChange={(event) => changeShot(index, "image_prompt", event.target.value)} />
                  {shot.references.length > 0 && <p>References: {shot.references.map((file) => file.split("/").pop()).join(", ")}</p>}
                </details>
              </div>
            </article>
          ))}</div>
          <div className="actions footer-actions">
            <button className="button primary" disabled={busy || storyboard.shots.some((shot) => !shot.narration.trim() || !shot.image_prompt.trim())}
              onClick={approve}><Check size={18} /> {status?.approved && status.radio && !dirty ? "Open Radio Cut" : "Approve & Create Radio Cut"}</button>
          </div>
        </>}
      </section>}

      {screen === "radio" && <section>
        {heading("Radio Cut Preview", "Listen to the narration and timing before generating the pictures.")}
        {busy && !status?.radio && <Loading>Preparing the radio cut…</Loading>}
        {!busy && !status?.radio && <button className="button primary" onClick={() => retry("radio")}>Create Radio Cut</button>}
        {status?.radio && job && <>
          <div className="radio-grid">
            <section className="panel field-panel">
              <div className="section-title"><AudioLines size={20} /><h2>{storyboard?.title ?? "Narration Preview"}</h2></div>
              <audio controls preload="metadata" aria-label="Narration preview" src={API + jobUrl(job, "radio")} />
              {storyboard && <details className="transcript" open>
                <summary>Transcript</summary>
                {storyboard.shots.map((shot) => <p key={shot.id}>{shot.narration}</p>)}
              </details>}
            </section>
            <section className="panel field-panel">
              <div className="section-title"><h2>How did it sound?</h2></div>
              <label htmlFor="laughed">What made you laugh?</label>
              <textarea id="laughed" rows={3} maxLength={2000} value={feedback.laughed} onChange={(event) => { setFeedbackSaved(false); setFeedback({ ...feedback, laughed: event.target.value }); }} />
              <label htmlFor="confused">What confused you?</label>
              <textarea id="confused" rows={3} maxLength={2000} value={feedback.confused} onChange={(event) => { setFeedbackSaved(false); setFeedback({ ...feedback, confused: event.target.value }); }} />
              <button className="button secondary" disabled={busy} onClick={() => saveFeedback()}>Save Feedback</button>
              {feedbackSaved && <p role="status" className="gold">Feedback saved.</p>}
            </section>
          </div>
          <div className="actions footer-actions">
            <button className="button secondary" onClick={() => setScreen("storyboard")}>Edit Storyboard</button>
            <button className="button primary" disabled={busy} onClick={() => saveFeedback(true)}><Clapperboard size={18} /> Generate Film</button>
          </div>
        </>}
      </section>}

      {screen === "progress" && <section>
        {heading("Crafting Your Heritage Film", "Watch the four production stages as your film comes together.")}
        <div className="panel field-panel">
          <div className="progress-summary"><strong>Film progress</strong><span>{completed} of 4 complete</span></div>
          <progress aria-label="Film progress" value={completed} max={4} />
          <ul className="phase-list">
            {phaseDetails.map(({ key, label, Icon }) => {
              const state = status?.stages[key] ?? "pending";
              const count = Object.values(status?.shots ?? {}).filter((shot) => shot[key] === "done").length;
              return <li key={key}>
                <span className="phase-icon"><Icon size={20} /></span>
                <div><strong>{label}</strong>{state === "running" && count > 0 && storyboard && <p>{count} of {storyboard.shots.length} shots</p>}</div>
                <span className={`phase-status ${state}`}>{phaseText[state]}</span>
              </li>;
            })}
          </ul>
          <p className="privacy">The film includes a “Made with AI” end card.</p>
        </div>
        {!busy && status?.state !== "done" && <div className="actions footer-actions"><button className="button primary" onClick={() => retry("generate")}>Retry Film Generation</button></div>}
        {status?.downloads && <div className="actions footer-actions"><button className="button primary" onClick={() => setScreen("film")}>Open Film</button></div>}
      </section>}

      {screen === "film" && job && status?.downloads && <section>
        {heading("Your Heritage Film Is Ready", storyboard?.title)}
        <div className="film-panel panel">
          <div className="film-toolbar">
            <div className="actions" aria-label="Video aspect ratio">
              <button className="button secondary compact" aria-pressed={orientation === "vertical"} onClick={() => setOrientation("vertical")}>Vertical 9:16</button>
              <button className="button secondary compact" aria-pressed={orientation === "horizontal"} onClick={() => setOrientation("horizontal")}>Landscape 16:9</button>
            </div>
            <span className="ai-label">{status.ai_label ?? "Made with AI"}</span>
          </div>
          <div className="player-frame">
            <video key={orientation} controls playsInline preload="metadata" className={orientation}
              aria-label={`${orientation} film preview`} src={API + jobUrl(job, `preview/${orientation}`)} />
          </div>
          <div className="actions film-actions">
            <a className="button primary" href={API + jobUrl(job, `download/${orientation}`)}><Download size={18} /> Download MP4</a>
            <a className="button secondary" href={API + jobUrl(job, "download/srt")}>Download Captions</a>
            <button className="button secondary" onClick={share} disabled={pending}><Share2 size={17} /> Share Preview</button>
          </div>
          {status.score === "placeholder" && <p className="privacy">This film uses a temporary synthesized score.</p>}
        </div>
      </section>}
    </main>
    <footer className="site-footer"><div className="shell"><span>Heritage Studio</span><span>Family stories on film</span></div></footer>
  </>;
}
