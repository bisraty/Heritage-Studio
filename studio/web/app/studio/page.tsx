"use client";

import { useEffect, useRef, useState } from "react";
import type { FormEvent, ReactNode } from "react";
import { MotionConfig, motion } from "motion/react";
import {
  AudioLines, Check, Frame, Images, ListVideo, LoaderCircle, LockKeyhole, Upload, X,
} from "lucide-react";
import {
  API, ApiError, jobUrl, jsonBody, request, storageKey,
  type Action, type JobStatus, type Orientation, type Screen, type Storyboard, type StudioConfig,
} from "../api";
import { Brand, Footer } from "../chrome";
import { FinalReview, ProcessingHeading, ProcessingReview, RadioHeading, RadioReview } from "./review-screens";
import "./review.css";

const screens = [
  { key: "story", label: "Story Input" },
  { key: "storyboard", label: "Storyboard" },
  { key: "radio", label: "Radio Cut" },
  { key: "progress", label: "Processing" },
  { key: "film", label: "Final Film" },
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

function restoredScreen(status: JobStatus): Screen {
  if (status.state === "done") return "film";
  if (status.busy || status.state === "failed") return actionTarget[status.action ?? "draft"][0];
  if (status.radio || status.approved) return "radio";
  return "storyboard";
}

export default function Studio() {
  const [screen, setScreen] = useState<Screen>("story");
  const [restoring, setRestoring] = useState(true);
  const [job, setJob] = useState<string | null>(null);
  const [status, setStatus] = useState<JobStatus | null>(null);
  const [pollVersion, setPollVersion] = useState(0);
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
  const [orientation, setOrientation] = useState<Orientation>("horizontal");
  const [notice, setNotice] = useState("");
  const fileInput = useRef<HTMLInputElement>(null);
  const restore = useRef(false);
  const main = useRef<HTMLElement>(null);

  useEffect(() => {
    const saved = sessionStorage.getItem(storageKey);
    if (saved) {
      restore.current = true;
      setJob(saved);
    } else {
      setRestoring(false);
    }
  }, []);

  useEffect(() => {
    main.current?.focus({ preventScroll: true });
    window.scrollTo(0, 0);
  }, [screen]);

  useEffect(() => {
    if (restoring || screen !== "story" || config) return;
    const controller = new AbortController();
    request<StudioConfig>("/api/config", { signal: controller.signal })
      .then(setConfig).catch((cause) => { if (!controller.signal.aborted) setError(cause.message); });
    return () => controller.abort();
  }, [screen, config, restoring]);

  function acceptStatus(next: JobStatus) {
    setStatus((current) => current && current.updated_at > next.updated_at ? current : next);
    if (restore.current) {
      restore.current = false;
      setRestoring(false);
      setScreen(restoredScreen(next));
    } else if (next.state === "done") {
      setScreen((current) => current === "progress" ? "film" : current);
    }
  }

  useEffect(() => {
    if (!job) return;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    let failures = 0;
    async function poll() {
      try {
        const next = await request<JobStatus>(jobUrl(job!, "status"), { signal: controller.signal });
        if (controller.signal.aborted) return;
        setConnection("");
        acceptStatus(next);
        failures = 0;
        if (!next.busy) return;
      } catch (cause) {
        if (controller.signal.aborted) return;
        if (cause instanceof ApiError && cause.status === 404) {
          sessionStorage.removeItem(storageKey);
          setJob(null);
          setStatus(null);
          setStoryboard(null);
          setRestoring(false);
          setScreen("story");
          setError("This job has expired. Start a new story to continue.");
          return;
        }
        setConnection(cause instanceof Error ? cause.message : "Waiting for the local API.");
        failures += 1;
        if (failures >= 3) return;
      }
      timer = setTimeout(poll, 2500);
    }
    void poll();
    return () => { controller.abort(); clearTimeout(timer); };
  }, [job, pollVersion]);

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
    setStatus((current) => current && ({ ...current, busy: true, action, state: "generating", error: null }));
    setPollVersion((version) => version + 1);
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
    setRestoring(false);
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
    setOrientation("horizontal");
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
  const allowed: Record<Screen, boolean> = {
    story: !job, storyboard: Boolean(job), radio: Boolean(status?.approved),
    progress: status?.action === "generate" || status?.state === "done", film: Boolean(status?.downloads),
  };
  const completedSteps: Record<Screen, boolean> = {
    story: Boolean(job),
    storyboard: Boolean(status?.approved),
    radio: Boolean(status?.radio),
    progress: status?.state === "done",
    film: Boolean(status?.downloads),
  };

  return <MotionConfig reducedMotion="user">
    <a href="#studio-main" className="skip-link">Skip to content</a>
    <header className="site-header">
      <div className="shell brand-bar">
        <Brand />
        {job ? <button className="button ghost compact" disabled={busy} onClick={reset}>New Story</button> :
          <span className="local-mark"><LockKeyhole size={14} /> Local Studio</span>}
      </div>
    </header>

    <div className="shell workspace">
      {!restoring && screen === "progress" && <ProcessingHeading status={status} />}
      <div className="workflow panel">
        <nav aria-label="Film production steps">
          <ol>
            {screens.map(({ key, label }) => <li key={key} className={completedSteps[key] ? "complete" : undefined}>
              <button aria-current={screen === key ? "step" : undefined}
                className={screen === key ? "workflow-step active" : "workflow-step"}
                disabled={restoring || (!allowed[key] && screen !== key)}
                onClick={() => { setError(""); setScreen(key); }}>
                <span className="workflow-icon" aria-hidden="true">{completedSteps[key] && screen !== key ? <Check size={17} /> : <span className="workflow-dot" />}</span>
                <strong>{label}</strong>
                {completedSteps[key] && <span className="sr-only">Complete</span>}
              </button>
            </li>)}
          </ol>
        </nav>
      </div>
    <main className="workspace-main" id="studio-main" tabIndex={-1} ref={main}>
      {connection && <p className="banner" role="status">{connection}</p>}
      {connection && job && <button className="button secondary mb-4" onClick={() => setPollVersion((version) => version + 1)}>Refresh Job Status</button>}
      {error && <p className="banner error" role="alert">{error}</p>}
      {status?.error && !error && status.state === "failed" && <p className="banner error" role="alert">{status.error}</p>}
      {notice && <p className="banner" role="status">{notice}</p>}

      {restoring ? <Loading>Opening your workspace…</Loading> :
        <motion.div key={screen} initial={{ opacity: .75, y: 8 }} animate={{ opacity: 1, y: 0 }}
          transition={{ duration: .25, ease: "easeOut" }}>

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
          <p className="banner" role="status">Studio created a local draft from your story. Review the narration before approving.</p>}
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
        <RadioHeading job={job} ready={Boolean(status?.radio)} />
        {busy && !status?.radio && <Loading>Preparing the radio cut…</Loading>}
        {!busy && !status?.radio && <button className="button primary" onClick={() => retry("radio")}>Create Radio Cut</button>}
        {status?.radio && job && <RadioReview
          job={job} storyboard={storyboard} feedback={feedback} saved={feedbackSaved} busy={busy}
          setFeedback={(value) => { setFeedbackSaved(false); setFeedback(value); }}
          edit={() => setScreen("storyboard")} save={() => saveFeedback()} generate={() => saveFeedback(true)} />}
      </section>}

      {screen === "progress" && <ProcessingReview
        job={job} storyboard={storyboard} status={status} busy={busy}
        retry={() => retry("generate")} openFilm={() => setScreen("film")} />}

      {screen === "film" && job && status?.downloads && <FinalReview
        job={job} storyboard={storyboard} status={status} orientation={orientation}
        setOrientation={setOrientation} pending={pending} share={share} />}
        </motion.div>}
    </main>
    </div>
    <Footer />
  </MotionConfig>;
}
