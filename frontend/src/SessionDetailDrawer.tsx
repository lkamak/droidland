import { useEffect, useState } from "react";
import { SessionDetails, api } from "./api";

interface Props {
  activationId: number;
  onClose: () => void;
}

const VERDICT_COLOR: Record<string, string> = {
  pass: "var(--green)",
  fail: "var(--red)",
  needs_human: "var(--amber)",
};

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

export function SessionDetailDrawer({ activationId, onClose }: Props) {
  const [details, setDetails] = useState<SessionDetails | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadDetails = () => {
    setLoading(true);
    setError(null);
    api
      .activationSession(activationId)
      .then(setDetails)
      .catch((e) => {
        console.error("Failed to load session details:", e);
        setError(e.message || "Failed to load session details");
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadDetails();
    // Poll for updates every 5 seconds while session is running
    const interval = setInterval(() => {
      if (details?.activation?.status === "running") {
        loadDetails();
      }
    }, 5000);
    return () => clearInterval(interval);
  }, [activationId, details?.activation?.status]);

  return (
    <div className="drawer-overlay" onClick={onClose}>
      <div className="drawer" onClick={(e) => e.stopPropagation()}>
        <div className="drawer-header">
          <h2>Session Details</h2>
          <button className="close-btn" onClick={onClose}>
            ✕
          </button>
        </div>

        <div className="drawer-content">
          {loading && !details && <div className="empty">Loading session details...</div>}
          {error && <div className="error-message">{error}</div>}

          {details && (
            <>
              {/* Activation Info */}
              <section className="drawer-section">
                <h3>Activation</h3>
                <div className="info-grid">
                  <div className="info-item">
                    <span className="label">Expert:</span>
                    <strong>{details.activation.expert_slug}</strong>
                  </div>
                  <div className="info-item">
                    <span className="label">Reference:</span>
                    <span className="mono">{details.activation.external_ref}</span>
                  </div>
                  <div className="info-item">
                    <span className="label">Status:</span>
                    <Badge
                      label={details.activation.status}
                      color={
                        details.activation.status.startsWith("error")
                          ? "var(--red)"
                          : details.activation.status === "running"
                          ? "var(--green)"
                          : "var(--gray)"
                      }
                    />
                  </div>
                  {details.activation.app_url && (
                    <div className="info-item">
                      <span className="label">Factory:</span>
                      <a
                        href={details.activation.app_url}
                        target="_blank"
                        rel="noreferrer"
                        className="external-link"
                      >
                        open in app.factory.ai ↗
                      </a>
                    </div>
                  )}
                </div>
              </section>

              {/* Trigger Info */}
              {details.trigger && (
                <section className="drawer-section">
                  <h3>Trigger</h3>
                  <div className="info-grid">
                    <div className="info-item">
                      <span className="label">Source:</span>
                      <Badge label={details.trigger.source} color="var(--violet)" />
                    </div>
                    <div className="info-item">
                      <span className="label">Event:</span>
                      <span className="mono">{details.trigger.event_type}</span>
                    </div>
                    {details.trigger.prompt_template && (
                      <div className="info-item full-width">
                        <span className="label">Prompt Template:</span>
                        <pre className="code-block">{details.trigger.prompt_template}</pre>
                      </div>
                    )}
                  </div>
                </section>
              )}

              {/* Token Usage */}
              {details.session && (
                <section className="drawer-section">
                  <h3>Token & Credit Usage</h3>
                  <div className="info-grid">
                    <div className="info-item">
                      <span className="label">Input Tokens:</span>
                      <span className="mono">
                        {((details.session as any).inputTokens || 0).toLocaleString()}
                      </span>
                    </div>
                    <div className="info-item">
                      <span className="label">Output Tokens:</span>
                      <span className="mono">
                        {((details.session as any).outputTokens || 0).toLocaleString()}
                      </span>
                    </div>
                    <div className="info-item">
                      <span className="label">Total Credits:</span>
                      <strong className="mono">
                        ${((details.session as any).totalCreditsUsed || 0).toFixed(2)}
                      </strong>
                    </div>
                  </div>
                </section>
              )}

              {/* Verdict */}
              {details.verdict && (
                <section className="drawer-section">
                  <h3>Verdict</h3>
                  <div className="verdict-block">
                    <Badge
                      label={details.verdict.verdict}
                      color={VERDICT_COLOR[details.verdict.verdict] || "var(--gray)"}
                    />
                    {details.verdict.summary && (
                      <p className="verdict-summary">{details.verdict.summary}</p>
                    )}
                    {details.verdict.branch && (
                      <div className="info-item">
                        <span className="label">Branch:</span>
                        <span className="mono">{details.verdict.branch}</span>
                      </div>
                    )}
                    {details.verdict.pr_url && (
                      <div className="info-item">
                        <span className="label">PR:</span>
                        <a
                          href={details.verdict.pr_url}
                          target="_blank"
                          rel="noreferrer"
                          className="external-link"
                        >
                          {details.verdict.pr_url} ↗
                        </a>
                      </div>
                    )}
                  </div>
                </section>
              )}

              {/* Transcript */}
              <section className="drawer-section">
                <h3>Transcript</h3>
                {details.messages.length === 0 ? (
                  <div className="empty">No messages yet</div>
                ) : (
                  <div className="transcript">
                    {details.messages.map((msg, idx) => (
                      <div
                        key={idx}
                        className={`message ${msg.role === "user" ? "message-user" : "message-assistant"}`}
                      >
                        <div className="message-role">
                          {msg.role === "user" ? "User" : "Assistant"}
                        </div>
                        <div className="message-content">{msg.content}</div>
                        {msg.timestamp && (
                          <div className="message-timestamp">
                            {new Date(msg.timestamp).toLocaleString()}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </section>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
