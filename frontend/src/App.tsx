import { useEffect, useState } from "react";
import { Activation, Computer, Expert, Trigger, Usage, api } from "./api";
import { ExpertEditor } from "./ExpertEditor";
import { TriggerEditor } from "./TriggerEditor";
import { SessionDetailDrawer } from "./SessionDetailDrawer";

type Tab = "dashboard" | "catalog" | "triggers";

const AUTONOMY_COLOR: Record<string, string> = {
  off: "var(--gray)",
  low: "var(--blue)",
  medium: "var(--amber)",
  high: "var(--red)",
};

const SOURCE_COLOR: Record<string, string> = {
  github: "#8b949e",
  linear: "var(--violet)",
};

const STATUS_COLOR: Record<string, string> = {
  running: "var(--green)",
  pending: "var(--amber)",
  idle: "var(--gray)",
};

function statusColor(status: string): string {
  if (status.startsWith("error")) return "var(--red)";
  return STATUS_COLOR[status] ?? "var(--gray)";
}

function Badge({ label, color }: { label: string; color: string }) {
  return (
    <span
      className="badge"
      style={{ color, borderColor: color, background: `color-mix(in srgb, ${color} 14%, transparent)` }}
    >
      {label}
    </span>
  );
}

export function App() {
  const [tab, setTab] = useState<Tab>("dashboard");
  const [experts, setExperts] = useState<Expert[]>([]);
  const [triggers, setTriggers] = useState<Trigger[]>([]);
  const [activations, setActivations] = useState<Activation[]>([]);
  const [computers, setComputers] = useState<Computer[]>([]);
  const [usage, setUsage] = useState<Usage | null>(null);

  const refresh = () => {
    api.experts().then(setExperts).catch(console.error);
    api.triggers().then(setTriggers).catch(console.error);
    api.activations().then(setActivations).catch(console.error);
    api.computers().then(setComputers).catch(console.error);
    api.usage().then(setUsage).catch(console.error);
  };

  useEffect(() => {
    refresh();
    const es = api.subscribe((type) => {
      if (type === "activation") api.activations().then(setActivations).catch(console.error);
      if (type === "computers") api.computers().then(setComputers).catch(console.error);
      if (type === "sessions") api.usage().then(setUsage).catch(console.error);
    });
    return () => es.close();
  }, []);

  return (
    <div className="shell">
      <div className="brand">
        <div className="logo" />
        <h1>Droidland</h1>
      </div>
      <p className="subtitle">
        Orchestrate Factory expert droids: catalog, signal-driven triggers, and live session health.
      </p>

      <nav className="tabs">
        {(["dashboard", "catalog", "triggers"] as Tab[]).map((t) => (
          <button key={t} className={tab === t ? "active" : ""} onClick={() => setTab(t)}>
            {t}
          </button>
        ))}
      </nav>

      {tab === "catalog" && <Catalog experts={experts} onChanged={refresh} />}
      {tab === "triggers" && (
        <Triggers triggers={triggers} experts={experts} onChanged={refresh} />
      )}
      {tab === "dashboard" && (
        <Dashboard activations={activations} computers={computers} usage={usage} />
      )}
    </div>
  );
}

function Catalog({ experts, onChanged }: { experts: Expert[]; onChanged: () => void }) {
  const [editing, setEditing] = useState<Expert | null>(null);
  const [creating, setCreating] = useState(false);

  const close = () => {
    setEditing(null);
    setCreating(false);
  };
  const saved = () => {
    close();
    onChanged();
  };
  const remove = async (slug: string) => {
    if (!confirm(`Delete expert "${slug}"?`)) return;
    await api.deleteExpert(slug).catch((e) => alert(e.message));
    onChanged();
  };

  if (creating || editing) {
    return <ExpertEditor initial={editing} onSaved={saved} onCancel={close} />;
  }

  return (
    <div>
      <div className="catalog-head">
        <h2>Experts</h2>
        <button className="primary" onClick={() => setCreating(true)}>
          + New expert
        </button>
      </div>
      {experts.length === 0 && <div className="empty">No experts yet. Create one to start.</div>}
      <div className="grid">
        {experts.map((e) => (
          <div key={e.slug} className="card">
            <div className="card-head">
              <span className="name">{e.name}</span>
              <span className="card-actions">
                <button onClick={() => setEditing(e)}>edit</button>
                <button className="danger" onClick={() => remove(e.slug)}>
                  delete
                </button>
              </span>
            </div>
            <p>{e.description}</p>
            <div className="row" style={{ marginBottom: 8 }}>
              <Badge
                label={`autonomy: ${e.autonomy}`}
                color={AUTONOMY_COLOR[e.autonomy] ?? "var(--gray)"}
              />
              <Badge label={e.interaction_mode} color="var(--accent)" />
              {e.run_in_worktree && <Badge label="worktree" color="var(--blue)" />}
            </div>
            <div className="row">
              {e.integrations.length === 0 && <span className="chip">no integrations</span>}
              {e.integrations.map((i) => (
                <span key={i} className="chip" style={{ color: SOURCE_COLOR[i] ?? "var(--muted)" }}>
                  {i}
                </span>
              ))}
              {e.skills.map((s) => (
                <span key={s} className="chip">
                  {s}
                </span>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function Triggers({
  triggers,
  experts,
  onChanged,
}: {
  triggers: Trigger[];
  experts: Expert[];
  onChanged: () => void;
}) {
  const [editing, setEditing] = useState<Trigger | null>(null);
  const [creating, setCreating] = useState(false);
  const [busy, setBusy] = useState(false);

  const close = () => {
    setEditing(null);
    setCreating(false);
  };
  const saved = () => {
    close();
    onChanged();
  };

  const toggle = async (t: Trigger) => {
    setBusy(true);
    await api
      .updateTrigger(t.id, { ...t, enabled: !t.enabled })
      .catch((e) => alert(e.message));
    setBusy(false);
    onChanged();
  };

  const remove = async (t: Trigger) => {
    if (!confirm(`Delete trigger #${t.id}?`)) return;
    await api.deleteTrigger(t.id).catch((e) => alert(e.message));
    onChanged();
  };

  const test = async (t: Trigger) => {
    try {
      const a = await api.testTrigger(t.id, {
        external_ref: `manual-${Date.now()}`,
        title: "Manual test",
        payload: t.condition,
      });
      alert(`Fired ${t.expert_slug}. Session ${a.factory_session_id || "(pending)"}.`);
      onChanged();
    } catch (e) {
      alert((e as Error).message);
    }
  };

  if (creating || editing) {
    return (
      <TriggerEditor initial={editing} experts={experts} onSaved={saved} onCancel={close} />
    );
  }

  return (
    <div>
      <div className="catalog-head">
        <h2>Triggers</h2>
        <button className="primary" onClick={() => setCreating(true)}>
          + New trigger
        </button>
      </div>
      {triggers.length === 0 && <div className="empty">No triggers configured yet.</div>}
      {triggers.length > 0 && (
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>source</th>
              <th>event</th>
              <th>condition</th>
              <th>expert</th>
              <th>status</th>
              <th>actions</th>
            </tr>
          </thead>
          <tbody>
            {triggers.map((t) => (
              <tr key={t.id}>
                <td>{t.id}</td>
                <td>
                  <Badge label={t.source} color={SOURCE_COLOR[t.source] ?? "var(--muted)"} />
                </td>
                <td className="mono">{t.event_type}</td>
                <td className="mono">{JSON.stringify(t.condition)}</td>
                <td>{t.expert_slug}</td>
                <td>
                  <Badge
                    label={t.enabled ? "enabled" : "disabled"}
                    color={t.enabled ? "var(--green)" : "var(--gray)"}
                  />
                </td>
                <td className="card-actions">
                  <button onClick={() => test(t)}>test</button>
                  <button onClick={() => toggle(t)} disabled={busy}>
                    {t.enabled ? "disable" : "enable"}
                  </button>
                  <button onClick={() => setEditing(t)}>edit</button>
                  <button className="danger" onClick={() => remove(t)}>
                    delete
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

function Dashboard({
  activations,
  computers,
  usage,
}: {
  activations: Activation[];
  computers: Computer[];
  usage: Usage | null;
}) {
  const [selectedActivation, setSelectedActivation] = useState<number | null>(null);

  return (
    <div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1.5rem", marginBottom: "2rem" }}>
        <ComputersPanel computers={computers} />
        <UsagePanel usage={usage} />
      </div>
      <h2>Recent activations</h2>
      {activations.length === 0 && <div className="empty">No activations yet.</div>}
      {activations.map((a) => (
        <div key={a.id} className="activation" onClick={() => setSelectedActivation(a.id)}>
          <span className="row">
            <span className="dot" style={{ background: statusColor(a.status) }} />
            <strong>{a.expert_slug}</strong>
            <span className="muted" style={{ color: "var(--muted)" }}>&rarr;</span>
            <span className="mono">{a.external_ref}</span>
          </span>
          <span className="row">
            <Badge label={a.status} color={statusColor(a.status)} />
            {a.app_url && (
              <a 
                href={a.app_url} 
                target="_blank" 
                rel="noreferrer"
                onClick={(e) => e.stopPropagation()}
              >
                open in app.factory.ai &#8599;
              </a>
            )}
          </span>
        </div>
      ))}

      {selectedActivation !== null && (
        <SessionDetailDrawer
          activationId={selectedActivation}
          onClose={() => setSelectedActivation(null)}
        />
      )}
    </div>
  );
}

function ComputersPanel({ computers }: { computers: Computer[] }) {
  return (
    <div className="card">
      <h3>Droid Computers</h3>
      {computers.length === 0 && <div className="empty">No computers found.</div>}
      {computers.map((c) => {
        const repos = JSON.parse(c.repos_json || "[]") as string[];
        const stateColor = c.state === "running" ? "var(--green)" : "var(--gray)";
        return (
          <div key={c.id} style={{ marginBottom: "1rem", paddingBottom: "1rem", borderBottom: "1px solid var(--border)" }}>
            <div className="row" style={{ marginBottom: "0.5rem" }}>
              <span className="dot" style={{ background: stateColor }} />
              <strong>{c.provider}</strong>
              <Badge label={c.state} color={stateColor} />
            </div>
            <div className="mono" style={{ fontSize: "0.85rem", color: "var(--muted)" }}>
              {repos.length > 0 ? repos.join(", ") : "no repos"}
            </div>
            {c.last_seen && (
              <div style={{ fontSize: "0.75rem", color: "var(--muted)", marginTop: "0.25rem" }}>
                last seen: {new Date(c.last_seen).toLocaleString()}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

function UsagePanel({ usage }: { usage: Usage | null }) {
  if (!usage) return <div className="card"><h3>Usage</h3><div className="empty">Loading...</div></div>;

  return (
    <div className="card">
      <h3>Token & Credit Usage</h3>
      <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
        <div className="row" style={{ justifyContent: "space-between" }}>
          <span>Total Sessions:</span>
          <strong>{usage.total_sessions}</strong>
        </div>
        <div className="row" style={{ justifyContent: "space-between" }}>
          <span>Active:</span>
          <Badge label={String(usage.active_sessions)} color="var(--green)" />
        </div>
        {usage.stale_sessions > 0 && (
          <div className="row" style={{ justifyContent: "space-between" }}>
            <span>Stale:</span>
            <Badge label={String(usage.stale_sessions)} color="var(--amber)" />
          </div>
        )}
        {usage.errored_sessions > 0 && (
          <div className="row" style={{ justifyContent: "space-between" }}>
            <span>Errored:</span>
            <Badge label={String(usage.errored_sessions)} color="var(--red)" />
          </div>
        )}
        <div style={{ borderTop: "1px solid var(--border)", paddingTop: "0.75rem", marginTop: "0.25rem" }}>
          <div className="row" style={{ justifyContent: "space-between", marginBottom: "0.5rem" }}>
            <span>Input Tokens:</span>
            <span className="mono">{usage.total_input_tokens.toLocaleString()}</span>
          </div>
          <div className="row" style={{ justifyContent: "space-between", marginBottom: "0.5rem" }}>
            <span>Output Tokens:</span>
            <span className="mono">{usage.total_output_tokens.toLocaleString()}</span>
          </div>
          <div className="row" style={{ justifyContent: "space-between" }}>
            <span>Total Credits:</span>
            <strong className="mono">${usage.total_credits.toFixed(2)}</strong>
          </div>
        </div>
      </div>
    </div>
  );
}
