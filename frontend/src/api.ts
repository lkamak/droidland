export interface Expert {
  slug: string;
  name: string;
  description: string;
  model: string;
  autonomy: string;
  interaction_mode: string;
  skills: string[];
  integrations: string[];
  run_in_worktree: boolean;
  prompt: string;
  file_path?: string;
}

export interface Trigger {
  id: number;
  source: string;
  event_type: string;
  condition: Record<string, unknown>;
  expert_slug: string;
  target_repo: string;
  cwd: string;
  prompt_template: string;
  enabled: boolean;
}

export interface Activation {
  id: number;
  expert_slug: string;
  external_ref: string;
  factory_session_id: string;
  app_url: string;
  status: string;
  created_at: string;
}

export interface Computer {
  id: number;
  factory_computer_id: string;
  provider: string;
  state: string;
  repos_json: string;
  last_seen: string;
  updated_at: string;
}

export interface Usage {
  total_input_tokens: number;
  total_output_tokens: number;
  total_credits: number;
  total_sessions: number;
  active_sessions: number;
  stale_sessions: number;
  errored_sessions: number;
}

export interface Message {
  role: string;
  content: string;
  timestamp?: string;
}

export interface SessionDetails {
  activation: Activation;
  session: Record<string, unknown>;
  messages: Message[];
  verdict: {
    verdict: string;
    branch?: string;
    pr_url?: string;
    summary?: string;
  } | null;
  trigger: Trigger | null;
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`/api${path}`);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

async function send<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(`/api${path}`, {
    method,
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {
      // keep status text
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

export type ExpertPayload = Omit<Expert, never>;

export interface TriggerPayload {
  source: string;
  event_type: string;
  condition: Record<string, unknown>;
  expert_slug: string;
  target_repo: string;
  cwd: string;
  prompt_template: string;
  enabled: boolean;
}

export const api = {
  health: () => get<Record<string, unknown>>("/health"),
  experts: () => get<Expert[]>("/experts"),
  createExpert: (e: ExpertPayload) => send<Expert>("POST", "/experts", e),
  updateExpert: (slug: string, e: Omit<ExpertPayload, "slug">) =>
    send<Expert>("PUT", `/experts/${slug}`, e),
  deleteExpert: (slug: string) => send<{ deleted: string }>("DELETE", `/experts/${slug}`),
  triggers: () => get<Trigger[]>("/triggers"),
  createTrigger: (t: TriggerPayload) => send<{ id: number }>("POST", "/triggers", t),
  updateTrigger: (id: number, t: TriggerPayload) =>
    send<{ id: number }>("PUT", `/triggers/${id}`, t),
  deleteTrigger: (id: number) => send<{ deleted: number }>("DELETE", `/triggers/${id}`),
  testTrigger: (id: number, event: Record<string, unknown>) =>
    send<Activation>("POST", `/triggers/${id}/test`, event),
  activations: () => get<Activation[]>("/activations"),
  activationSession: (id: number) => get<SessionDetails>(`/activations/${id}/session`),
  sessions: () => get<Record<string, unknown>[]>("/sessions"),
  computers: () => get<Computer[]>("/computers"),
  usage: () => get<Usage>("/usage"),
  subscribe(onEvent: (type: string, data: unknown) => void): EventSource {
    const es = new EventSource("/api/stream");
    ["activation", "sessions", "computers", "ping"].forEach((type) =>
      es.addEventListener(type, (e) => onEvent(type, JSON.parse((e as MessageEvent).data))),
    );
    return es;
  },
};
