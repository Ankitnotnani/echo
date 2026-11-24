import { API_URL } from "../lib/config";
import type { ChatMetadata, HealthState, ThreadItem } from "../lib/types";

function median(values: number[]): number | null {
  if (!values.length) return null;
  const s = [...values].sort((a, b) => a - b);
  const mid = Math.floor(s.length / 2);
  return s.length % 2 ? s[mid] : Math.round((s[mid - 1] + s[mid]) / 2);
}

export function Overview({ health, items, sessionId }: { health: HealthState; items: ThreadItem[]; sessionId: string }) {
  const requests = items.filter((i): i is Extract<ThreadItem, { kind: "assistant" }> => i.kind === "assistant");
  const metas = requests.map((r) => r.meta as Partial<ChatMetadata>);
  const live = metas.filter((m) => m.resolution_source === "LIVE_INFERENCE").map((m) => m.latency_ms ?? 0);
  const cache = metas.filter((m) => m.resolution_source === "LLM_CACHE").map((m) => m.latency_ms ?? 0);
  const liveMed = median(live);
  const cacheMed = median(cache);
  const h = health.state === "ok" ? health.data : null;

  return (
    <div className="overview">
      <section className="ov-card">
        <h2>Gateway status</h2>
        <dl className="ov-grid">
          <div><dt>Backend</dt><dd className={h ? "is-good" : "is-bad"}>{h ? "Healthy" : health.state === "checking" ? "Checking…" : "Unreachable"}</dd></div>
          <div><dt>API keys in pool</dt><dd>{h ? h.keys_configured : "–"}</dd></div>
          <div><dt>Model</dt><dd className="mono">{h?.model ?? "–"}</dd></div>
          <div><dt>LiteLLM cache</dt><dd>{h ? (h.cache_enabled ? "Enabled" : "Disabled") : "–"}</dd></div>
          <div><dt>Failure simulation</dt><dd>{h ? (h.failure_simulation_enabled ? "Enabled" : "Disabled") : "–"}</dd></div>
          <div><dt>API URL</dt><dd className="mono">{API_URL}</dd></div>
        </dl>
      </section>

      <section className="ov-card">
        <h2>This session</h2>
        <p className="ov-sub mono">{sessionId}</p>
        <div className="ov-stats">
          <div><span className="ov-num">{liveMed ?? "–"}{liveMed !== null && <small> ms</small>}</span><span className="ov-lbl">Median live latency</span></div>
          <div><span className="ov-num is-cache">{cacheMed ?? "–"}{cacheMed !== null && <small> ms</small>}</span><span className="ov-lbl">Median cache latency</span></div>
          <div><span className="ov-num">{cache.length}/{metas.length}</span><span className="ov-lbl">Requests from cache</span></div>
        </div>
        {metas.length === 0 ? (
          <p className="ov-empty">No requests yet. Send a message in Chat Mode and each request appears here with its own metrics.</p>
        ) : (
          <div className="ov-table-wrap">
            <table className="ov-table">
              <thead>
                <tr><th>#</th><th>Source</th><th>Latency</th><th>In</th><th>Out</th><th>Key</th><th>Failovers</th></tr>
              </thead>
              <tbody>
                {metas.map((m, i) => (
                  <tr key={i}>
                    <td>{i + 1}</td>
                    <td><span className={`src ${m.resolution_source === "LLM_CACHE" ? "is-cache" : "is-live"}`}>{m.resolution_source}</span></td>
                    <td>{m.latency_ms} ms</td>
                    <td>{m.input_tokens}</td>
                    <td>{m.output_tokens}</td>
                    <td className="mono">{m.key_id ?? "—"}</td>
                    <td>{m.fallback_attempts ?? 0}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="ov-note">Tokens are per request only; there is deliberately no running total.</p>
          </div>
        )}
      </section>
    </div>
  );
}
