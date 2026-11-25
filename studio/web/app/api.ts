export const API = (process.env.NEXT_PUBLIC_STUDIO_API_URL || "http://127.0.0.1:8000").replace(/\/$/, "");

export type Stage = "narration" | "pictures" | "music" | "edit";
export type Action = "draft" | "radio" | "generate";
export const storageKey = "heritage-studio-current-job";
export type Screen = "story" | "storyboard" | "radio" | "progress" | "film";
export type Orientation = "vertical" | "horizontal";

export interface StudioConfig {
  consent: string;
  privacy_note: string;
  max_photos: number;
  max_photo_bytes: number;
  retention_hours: number;
}

export interface Shot {
  id: number;
  duration_s: number;
  shot_size: string;
  reason: string;
  narration: string;
  image_prompt: string;
  references: string[];
}

export interface Storyboard {
  title: string;
  shots: Shot[];
}

export interface JobStatus {
  state: "created" | "storyboard_drafted" | "storyboard_approved" | "radio_ready" | "generating" | "done" | "failed";
  approved?: boolean;
  action?: Action;
  busy: boolean;
  current_stage: string | null;
  error: string | null;
  stages: Record<Stage, "pending" | "running" | "done" | "failed">;
  updated_at: string;
  shots: Record<string, Partial<Record<Stage, "done">>>;
  radio?: string | null;
  downloads?: Record<string, string> | null;
  ai_label?: string;
  score?: "imported" | "placeholder";
  draft_source?: "gemini" | "local";
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

export async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(API + path, { cache: "no-store", ...options });
  } catch (error) {
    if (options.signal?.aborted) throw error;
    throw new ApiError(0, "Studio couldn’t reach the local API. Check that the backend is running and try again.");
  }
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = body?.detail;
    const message = typeof detail === "string" ? detail :
      Array.isArray(detail) ? detail.map((item) => item.msg).join(". ") : "The request could not be completed.";
    throw new ApiError(response.status, message);
  }
  if (body === null) throw new ApiError(response.status, "The local API returned an unexpected response.");
  return body as T;
}

export function jsonBody(value: unknown, method: "PUT" | "POST"): RequestInit {
  return { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(value) };
}

export function jobUrl(job: string, suffix: string) {
  return `/api/jobs/${encodeURIComponent(job)}/${suffix}`;
}
