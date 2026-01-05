import { useEffect, useMemo, useState } from "react";
import { apiGet } from "../api/client";

type DashRow = {
  run_id: string;
  campaign_id: string;
  campaign_name: string | null;
  customer_id: string;
  customer_name: string | null;
  status: string;
  started_at: string | null;
  finished_at: string | null;
  has_log: boolean;
  has_result: boolean;
};

function formatTehran(isoUtc: string | null): string {
  if (!isoUtc) return "-";
  const d = new Date(isoUtc);
  return new Intl.DateTimeFormat("fa-IR", {
    timeZone: "Asia/Tehran",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(d);
}

const API_BASE = "http://127.0.0.1:8000/api";

export default function Dashboard() {
  const [rows, setRows] = useState<DashRow[]>([]);
  const [status, setStatus] = useState<string>("");
  const [customerId, setCustomerId] = useState<string>("");
  const [q, setQ] = useState<string>("");

  const filtered = useMemo(() => rows, [rows]);

  async function load() {
    const params = new URLSearchParams();
    if (status) params.set("status", status);
    if (customerId) params.set("customer_id", customerId);
    if (q.trim()) params.set("q", q.trim());
    params.set("limit", "300");

    const data = await apiGet<DashRow[]>(`/dashboard/runs?${params.toString()}`);
    setRows(data);
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div style={{ padding: 16 }}>
      <h2 style={{ marginTop: 0 }}>Dashboard</h2>

      <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center" }}>
        <select value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">All statuses</option>
          <option value="success">success</option>
          <option value="failed">failed</option>
          <option value="running">running</option>
        </select>

        <input
          value={customerId}
          onChange={(e) => setCustomerId(e.target.value)}
          placeholder="Customer ID (optional)"
          style={{ padding: 8, borderRadius: 8, border: "1px solid #ddd", minWidth: 280 }}
        />

        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search (customer/campaign name)"
          style={{ padding: 8, borderRadius: 8, border: "1px solid #ddd", minWidth: 280 }}
        />

        <button onClick={load}>Apply</button>
        <button onClick={() => { setStatus(""); setCustomerId(""); setQ(""); }}>Clear</button>
      </div>

      <div style={{ marginTop: 12, overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr>
              <th align="left" style={{ borderBottom: "1px solid #eee", padding: "8px 0" }}>Run At (Tehran)</th>
              <th align="left" style={{ borderBottom: "1px solid #eee", padding: "8px 0" }}>Customer</th>
              <th align="left" style={{ borderBottom: "1px solid #eee", padding: "8px 0" }}>Campaign</th>
              <th align="left" style={{ borderBottom: "1px solid #eee", padding: "8px 0" }}>Status</th>
              <th align="left" style={{ borderBottom: "1px solid #eee", padding: "8px 0" }}>Run ID</th>
              <th align="left" style={{ borderBottom: "1px solid #eee", padding: "8px 0" }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((r) => (
              <tr key={r.run_id} style={{ borderBottom: "1px solid #f4f4f4" }}>
                <td style={{ padding: "8px 0", fontFamily: "monospace", fontSize: 12 }}>
                  {formatTehran(r.started_at)}
                </td>
                <td style={{ padding: "8px 0" }}>{r.customer_name || "-"}</td>
                <td style={{ padding: "8px 0" }}>{r.campaign_name || "-"}</td>
                <td style={{ padding: "8px 0" }}>{r.status}</td>
                <td style={{ padding: "8px 0", fontFamily: "monospace", fontSize: 12 }}>{r.run_id}</td>
                <td style={{ padding: "8px 0", display: "flex", gap: 8, flexWrap: "wrap" }}>
                  {r.has_log && (
                    <button onClick={() => window.open(`${API_BASE}/runs/${r.run_id}/log/download`, "_blank")}>
                      Download log
                    </button>
                  )}
                  {r.has_result && (
                    <button onClick={() => window.open(`${API_BASE}/runs/${r.run_id}/result/download`, "_blank")}>
                      Send Result
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {filtered.length === 0 && (
              <tr><td colSpan={6} style={{ padding: "12px 0", color: "#666" }}>No runs.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
