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
}

export interface Trigger {
  id: number;
  source: string;
  event_type: string;
  condition: Record<string, unknown>;
  expert_slug: string;
  target_repo: string;
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

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`/api${path}`);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

export const api = {
  health: () => get<Record<string, unknown>>("/health"),
  experts: () => get<Expert[]>("/experts"),
  triggers: () => get<Trigger[]>("/triggers"),
  activations: () => get<Activation[]>("/activations"),
  sessions: () => get<Record<string, unknown>[]>("/sessions"),
  subscribe(onEvent: (type: string, data: unknown) => void): EventSource {
    const es = new EventSource("/api/stream");
    ["activation", "sessions", "ping"].forEach((type) =>
      es.addEventListener(type, (e) => onEvent(type, JSON.parse((e as MessageEvent).data))),
    );
    return es;
  },
};
