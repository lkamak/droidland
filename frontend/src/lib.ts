export const AUTONOMY_LEVELS = ["off", "low", "medium", "high"] as const;
export const INTERACTION_MODES = ["auto", "spec", "agi", "mission"] as const;

export type Autonomy = (typeof AUTONOMY_LEVELS)[number];
export type InteractionMode = (typeof INTERACTION_MODES)[number];

const SLUG_RE = /^[a-z0-9][a-z0-9-]*$/;

export function slugify(name: string): string {
  return name
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

/** Parse a comma- or newline-separated string into a clean list. */
export function parseList(value: string): string[] {
  return value
    .split(/[,\n]/)
    .map((s) => s.trim())
    .filter(Boolean);
}

export interface ExpertForm {
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
}

export function validateExpert(form: Pick<ExpertForm, "slug" | "name" | "autonomy" | "interaction_mode">): string[] {
  const errors: string[] = [];
  if (!form.name.trim()) errors.push("name is required");
  if (!SLUG_RE.test(form.slug)) errors.push("slug must be lowercase alphanumeric with dashes");
  if (!AUTONOMY_LEVELS.includes(form.autonomy as Autonomy)) errors.push("invalid autonomy");
  if (!INTERACTION_MODES.includes(form.interaction_mode as InteractionMode))
    errors.push("invalid interaction mode");
  return errors;
}

export function emptyExpertForm(): ExpertForm {
  return {
    slug: "",
    name: "",
    description: "",
    model: "",
    autonomy: "high",
    interaction_mode: "auto",
    skills: [],
    integrations: [],
    run_in_worktree: false,
    prompt: "",
  };
}

// --- Triggers ---

export const TRIGGER_SOURCES = ["github", "linear"] as const;
export const EVENT_TYPES_BY_SOURCE: Record<string, string[]> = {
  github: ["pull_request"],
  linear: ["issue"],
};

// Event fields available as {{variables}} in a trigger's task prompt, by source.
export const EVENT_VARS_BY_SOURCE: Record<string, string[]> = {
  github: ["external_ref", "title", "url", "repo", "number", "head", "base", "author", "action"],
  linear: ["external_ref", "identifier", "title", "url", "state"],
};

export function eventVarsForSource(source: string): string[] {
  return EVENT_VARS_BY_SOURCE[source] ?? [];
}

export interface TriggerForm {
  source: string;
  event_type: string;
  conditionText: string;
  expert_slug: string;
  target_repo: string;
  cwd: string;
  prompt_template: string;
  enabled: boolean;
}

export interface ParsedCondition {
  ok: boolean;
  value: Record<string, unknown>;
  error?: string;
}

/** Parse the condition JSON text into a flat object of scalar/string matchers. */
export function parseCondition(text: string): ParsedCondition {
  const trimmed = text.trim();
  if (!trimmed) return { ok: true, value: {} };
  let parsed: unknown;
  try {
    parsed = JSON.parse(trimmed);
  } catch {
    return { ok: false, value: {}, error: "condition must be valid JSON" };
  }
  if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) {
    return { ok: false, value: {}, error: "condition must be a JSON object" };
  }
  return { ok: true, value: parsed as Record<string, unknown> };
}

export function validateTrigger(form: TriggerForm, expertSlugs: string[]): string[] {
  const errors: string[] = [];
  if (!TRIGGER_SOURCES.includes(form.source as (typeof TRIGGER_SOURCES)[number]))
    errors.push("invalid source");
  if (!form.event_type.trim()) errors.push("event type is required");
  if (!expertSlugs.includes(form.expert_slug)) errors.push("select a valid expert");
  const cond = parseCondition(form.conditionText);
  if (!cond.ok) errors.push(cond.error ?? "invalid condition");
  return errors;
}

export function emptyTriggerForm(): TriggerForm {
  return {
    source: "github",
    event_type: "pull_request",
    conditionText: '{"action": "opened"}',
    expert_slug: "",
    target_repo: "",
    cwd: "",
    prompt_template: "Review {{external_ref}}: {{title}}",
    enabled: true,
  };
}
