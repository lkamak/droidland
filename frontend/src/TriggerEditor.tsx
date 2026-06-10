import { useState } from "react";
import { Expert, Trigger, api } from "./api";
import {
  EVENT_TYPES_BY_SOURCE,
  TRIGGER_SOURCES,
  TriggerForm,
  emptyTriggerForm,
  parseCondition,
  validateTrigger,
} from "./lib";

interface Props {
  initial: Trigger | null; // null => create new
  experts: Expert[];
  onSaved: () => void;
  onCancel: () => void;
}

function toForm(t: Trigger | null): TriggerForm {
  if (!t) return emptyTriggerForm();
  return {
    source: t.source,
    event_type: t.event_type,
    conditionText: JSON.stringify(t.condition),
    expert_slug: t.expert_slug,
    target_repo: t.target_repo,
    cwd: t.cwd ?? "",
    prompt_template: t.prompt_template,
    enabled: t.enabled,
  };
}

export function TriggerEditor({ initial, experts, onSaved, onCancel }: Props) {
  const isNew = initial === null;
  const [form, setForm] = useState<TriggerForm>(toForm(initial));
  const [errors, setErrors] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);

  const set = <K extends keyof TriggerForm>(key: K, value: TriggerForm[K]) =>
    setForm((f) => ({ ...f, [key]: value }));

  const submit = async () => {
    const slugs = experts.map((e) => e.slug);
    const errs = validateTrigger(form, slugs);
    if (errs.length) {
      setErrors(errs);
      return;
    }
    const payload = {
      source: form.source,
      event_type: form.event_type,
      condition: parseCondition(form.conditionText).value,
      expert_slug: form.expert_slug,
      target_repo: form.target_repo,
      cwd: form.cwd,
      prompt_template: form.prompt_template,
      enabled: form.enabled,
    };
    setSaving(true);
    try {
      if (isNew) await api.createTrigger(payload);
      else await api.updateTrigger(initial!.id, payload);
      onSaved();
    } catch (e) {
      setErrors([(e as Error).message]);
    } finally {
      setSaving(false);
    }
  };

  const events = EVENT_TYPES_BY_SOURCE[form.source] ?? [];

  return (
    <div className="card editor">
      <h2>{isNew ? "New trigger" : `Edit trigger #${initial!.id}`}</h2>

      <div className="form-row">
        <label>
          Source
          <select
            value={form.source}
            onChange={(e) => {
              const source = e.target.value;
              set("source", source);
              set("event_type", (EVENT_TYPES_BY_SOURCE[source] ?? [""])[0]);
            }}
          >
            {TRIGGER_SOURCES.map((s) => (
              <option key={s}>{s}</option>
            ))}
          </select>
        </label>
        <label>
          Event type
          <select value={form.event_type} onChange={(e) => set("event_type", e.target.value)}>
            {events.map((ev) => (
              <option key={ev}>{ev}</option>
            ))}
          </select>
        </label>
        <label className="check">
          <input
            type="checkbox"
            checked={form.enabled}
            onChange={(e) => set("enabled", e.target.checked)}
          />
          enabled
        </label>
      </div>

      <label>
        Condition (JSON object)
        <input value={form.conditionText} onChange={(e) => set("conditionText", e.target.value)} />
      </label>

      <label>
        Expert
        <select value={form.expert_slug} onChange={(e) => set("expert_slug", e.target.value)}>
          <option value="">select an expert...</option>
          {experts.map((ex) => (
            <option key={ex.slug} value={ex.slug}>
              {ex.name} ({ex.slug})
            </option>
          ))}
        </select>
      </label>

      <div className="form-row">
        <label>
          Target repo (optional)
          <input value={form.target_repo} onChange={(e) => set("target_repo", e.target.value)} />
        </label>
        <label>
          Working dir (optional)
          <input value={form.cwd} onChange={(e) => set("cwd", e.target.value)} />
        </label>
      </div>

      <label>
        Prompt template
        <textarea
          rows={4}
          value={form.prompt_template}
          onChange={(e) => set("prompt_template", e.target.value)}
        />
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
