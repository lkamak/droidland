import { useEffect, useState } from "react";
import { Activation, Expert, Trigger, api } from "./api";

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

  const refresh = () => {
    api.experts().then(setExperts).catch(console.error);
    api.triggers().then(setTriggers).catch(console.error);
    api.activations().then(setActivations).catch(console.error);
  };

  useEffect(() => {
    refresh();
    const es = api.subscribe((type) => {
      if (type === "activation") api.activations().then(setActivations).catch(console.error);
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

      {tab === "catalog" && <Catalog experts={experts} />}
      {tab === "triggers" && <Triggers triggers={triggers} />}
      {tab === "dashboard" && <Dashboard activations={activations} />}
    </div>
  );
}

function Catalog({ experts }: { experts: Expert[] }) {
  if (experts.length === 0) return <div className="empty">No experts loaded.</div>;
  return (
    <div className="grid">
      {experts.map((e) => (
        <div key={e.slug} className="card">
          <div className="name">{e.name}</div>
          <p>{e.description}</p>
          <div className="row" style={{ marginBottom: 8 }}>
            <Badge label={`autonomy: ${e.autonomy}`} color={AUTONOMY_COLOR[e.autonomy] ?? "var(--gray)"} />
            <Badge label={e.interaction_mode} color="var(--accent)" />
            {e.run_in_worktree && <Badge label="worktree" color="var(--blue)" />}
          </div>
          <div className="row">
            {e.integrations.length === 0 && <span className="chip">no integrations</span>}
            {e.integrations.map((i) => (
              <span
                key={i}
                className="chip"
                style={{ color: SOURCE_COLOR[i] ?? "var(--muted)" }}
              >
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
  );
}

function Triggers({ triggers }: { triggers: Trigger[] }) {
  if (triggers.length === 0) return <div className="empty">No triggers configured yet.</div>;
  return (
    <table>
      <thead>
        <tr>
          <th>#</th>
          <th>source</th>
          <th>event</th>
          <th>condition</th>
          <th>expert</th>
          <th>status</th>
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
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function Dashboard({ activations }: { activations: Activation[] }) {
  return (
    <div>
      <h2>Recent activations</h2>
      {activations.length === 0 && <div className="empty">No activations yet.</div>}
      {activations.map((a) => (
        <div key={a.id} className="activation">
          <span className="row">
            <span className="dot" style={{ background: statusColor(a.status) }} />
            <strong>{a.expert_slug}</strong>
            <span className="muted" style={{ color: "var(--muted)" }}>&rarr;</span>
            <span className="mono">{a.external_ref}</span>
          </span>
          <span className="row">
            <Badge label={a.status} color={statusColor(a.status)} />
            {a.app_url && (
              <a href={a.app_url} target="_blank" rel="noreferrer">
                open in app.factory.ai &#8599;
              </a>
            )}
          </span>
        </div>
      ))}
    </div>
  );
}
