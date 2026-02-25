import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { apiGet } from "../api/client";

export default function RunLiveLogPage() {
  const { runId } = useParams();
  const [logText, setLogText] = useState("");
  const [error, setError] = useState("");
  const [autoRefresh, setAutoRefresh] = useState(true);

  async function loadLog() {
    if (!runId) return;
    try {
      const res = await apiGet<{ log: string }>(`/runs/${runId}/log`);
      setLogText(res.log || "");
      setError("");
    } catch (e: any) {
      setError(String(e?.message || e));
    }
  }

  useEffect(() => {
    loadLog();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runId]);

  useEffect(() => {
    if (!autoRefresh) return;
    const t = setInterval(loadLog, 3000);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoRefresh, runId]);

  return (
    <div style={{ display: "grid", gap: 10 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h2 style={{ margin: 0 }}>Live Log</h2>
        <Link to="/">Back to Dashboard</Link>
      </div>

      <div style={{ fontSize: 12, color: "#666" }}>
        Run ID: <code>{runId || "-"}</code>
      </div>

      <div style={{ display: "flex", gap: 8 }}>
        <button onClick={loadLog}>Refresh now</button>
        <button onClick={() => setAutoRefresh((v) => !v)}>{autoRefresh ? "Pause auto refresh" : "Resume auto refresh"}</button>
      </div>

      {error && <div style={{ color: "#b91c1c" }}>{error}</div>}

      <textarea
        readOnly
        value={logText}
        style={{
          width: "100%",
          minHeight: 520,
          fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
          fontSize: 12,
          borderRadius: 8,
          padding: 10,
          whiteSpace: "pre",
        }}
      />
    </div>
  );
}

