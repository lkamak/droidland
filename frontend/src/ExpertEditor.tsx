import { useState } from "react";
import { Expert, api } from "./api";
import {
  AUTONOMY_LEVELS,
  ExpertForm,
  INTERACTION_MODES,
  emptyExpertForm,
  parseList,
  slugify,
  validateExpert,
} from "./lib";

interface Props {
  initial: Expert | null; // null => create new
  onSaved: () => void;
  onCancel: () => void;
}

function toForm(e: Expert | null): ExpertForm {
  if (!e) return emptyExpertForm();
  return { ...e };
}

export function ExpertEditor({ initial, onSaved, onCancel }: Props) {
  const isNew = initial === null;
  const [form, setForm] = useState<ExpertForm>(toForm(initial));
  const [skillsText, setSkillsText] = useState((initial?.skills ?? []).join(", "));
  const [integrationsText, setIntegrationsText] = useState(
    (initial?.integrations ?? []).join(", "),
  );
  const [errors, setErrors] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);

  const set = <K extends keyof ExpertForm>(key: K, value: ExpertForm[K]) =>
    setForm((f) => ({ ...f, [key]: value }));

  const submit = async () => {
    const payload: ExpertForm = {
      ...form,
      skills: parseList(skillsText),
      integrations: parseList(integrationsText),
    };
    const errs = validateExpert(payload);
    if (errs.length) {
      setErrors(errs);
      return;
    }
    setSaving(true);
    try {
      if (isNew) {
        await api.createExpert(payload);
      } else {
        await api.updateExpert(payload.slug, {
          name: payload.name,
          description: payload.description,
          model: payload.model,
          autonomy: payload.autonomy,
          interaction_mode: payload.interaction_mode,
          skills: payload.skills,
          integrations: payload.integrations,
          run_in_worktree: payload.run_in_worktree,
          prompt: payload.prompt,
        });
      }
      onSaved();
    } catch (e) {
      setErrors([(e as Error).message]);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="card editor">
      <h2>{isNew ? "New expert" : `Edit: ${form.name}`}</h2>

      <label>
        Name
        <input
          value={form.name}
          onChange={(e) => {
            set("name", e.target.value);
            if (isNew) set("slug", slugify(e.target.value));
          }}
        />
      </label>

      <label>
        Slug
        <input
          value={form.slug}
          disabled={!isNew}
          onChange={(e) => set("slug", e.target.value)}
        />
      </label>

      <label>
        Description
        <input value={form.description} onChange={(e) => set("description", e.target.value)} />
      </label>

      <div className="form-row">
        <label>
          Autonomy
          <select value={form.autonomy} onChange={(e) => set("autonomy", e.target.value)}>
            {AUTONOMY_LEVELS.map((a) => (
              <option key={a}>{a}</option>
            ))}
          </select>
        </label>
        <label>
          Interaction mode
          <select
            value={form.interaction_mode}
            onChange={(e) => set("interaction_mode", e.target.value)}
          >
            {INTERACTION_MODES.map((m) => (
              <option key={m}>{m}</option>
            ))}
          </select>
        </label>
        <label className="check">
          <input
            type="checkbox"
            checked={form.run_in_worktree}
            onChange={(e) => set("run_in_worktree", e.target.checked)}
          />
          run in worktree
        </label>
      </div>

      <label>
        Model (optional)
        <input value={form.model} onChange={(e) => set("model", e.target.value)} />
      </label>

      <div className="form-row">
        <label>
          Skills / tools (comma separated)
          <input value={skillsText} onChange={(e) => setSkillsText(e.target.value)} />
        </label>
        <label>
          Integrations (comma separated)
          <input value={integrationsText} onChange={(e) => setIntegrationsText(e.target.value)} />
        </label>
      </div>

      <label>
        Persona prompt
        <textarea rows={8} value={form.prompt} onChange={(e) => set("prompt", e.target.value)} />
      </label>

      {errors.length > 0 && (
        <ul className="errors">
          {errors.map((er) => (
            <li key={er}>{er}</li>
          ))}
        </ul>
      )}

      <div className="actions">
        <button className="primary" onClick={submit} disabled={saving}>
          {saving ? "Saving..." : "Save"}
        </button>
        <button onClick={onCancel} disabled={saving}>
          Cancel
        </button>
      </div>
    </div>
  );
}
