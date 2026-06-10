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
    autonomy: "off",
    interaction_mode: "auto",
    skills: [],
    integrations: [],
    run_in_worktree: false,
    prompt: "",
  };
}
