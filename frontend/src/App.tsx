import { useEffect, useState } from "react";
import { Activation, Expert, Trigger, api } from "./api";

type Tab = "catalog" | "triggers" | "dashboard";

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
    <div style={{ fontFamily: "system-ui", maxWidth: 980, margin: "0 auto", padding: 24 }}>
      <h1>Droidland</h1>
      <nav style={{ display: "flex", gap: 12, marginBottom: 20 }}>
        {(["dashboard", "catalog", "triggers"] as Tab[]).map((t) => (
          <button key={t} onClick={() => setTab(t)} disabled={tab === t}>
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
  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
      {experts.map((e) => (
        <div key={e.slug} style={{ border: "1px solid #ddd", borderRadius: 8, padding: 12 }}>
          <strong>{e.name}</strong>
          <p style={{ color: "#555", fontSize: 14 }}>{e.description}</p>
          <div style={{ fontSize: 12, color: "#777" }}>
            autonomy: {e.autonomy} | mode: {e.interaction_mode} | worktree:{" "}
            {String(e.run_in_worktree)}
          </div>
          <div style={{ fontSize: 12 }}>integrations: {e.integrations.join(", ") || "none"}</div>
        </div>
      ))}
    </div>
  );
}

function Triggers({ triggers }: { triggers: Trigger[] }) {
  return (
    <table style={{ width: "100%", borderCollapse: "collapse" }}>
      <thead>
        <tr>
          <th align="left">#</th>
          <th align="left">source</th>
          <th align="left">event</th>
          <th align="left">condition</th>
          <th align="left">expert</th>
          <th align="left">enabled</th>
        </tr>
      </thead>
      <tbody>
        {triggers.map((t) => (
          <tr key={t.id} style={{ borderTop: "1px solid #eee" }}>
            <td>{t.id}</td>
            <td>{t.source}</td>
            <td>{t.event_type}</td>
            <td>{JSON.stringify(t.condition)}</td>
            <td>{t.expert_slug}</td>
            <td>{String(t.enabled)}</td>
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
      {activations.length === 0 && <p style={{ color: "#777" }}>No activations yet.</p>}
      {activations.map((a) => (
        <div
          key={a.id}
          style={{
            display: "flex",
            justifyContent: "space-between",
            borderBottom: "1px solid #eee",
            padding: "8px 0",
          }}
        >
          <span>
            <strong>{a.expert_slug}</strong> &rarr; {a.external_ref}
          </span>
          <span>
            <em style={{ marginRight: 8 }}>{a.status}</em>
            {a.app_url && (
              <a href={a.app_url} target="_blank" rel="noreferrer">
                open in app.factory.ai
              </a>
            )}
          </span>
        </div>
      ))}
    </div>
  );
}
