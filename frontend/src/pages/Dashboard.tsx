import { useEffect, useMemo, useState } from "react";
import { apiGet } from "../api/client";
import { Link } from "react-router-dom";
import "./Dashboard.css";

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
  progress_current?: number | null;
  progress_total?: number | null;
  progress_pct?: number | null;
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
  const summary = useMemo(() => {
    const total = filtered.length;
    const running = filtered.filter((r) => r.status.toLowerCase() === "running").length;
    const success = filtered.filter((r) => r.status.toLowerCase() === "success").length;
    const failed = filtered.filter((r) => r.status.toLowerCase() === "failed").length;
    const successRate = total ? Math.round((success / total) * 100) : 0;
    return { total, running, success, failed, successRate };
  }, [filtered]);

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
    <div className="dash-page">
      <div className="dash-toolbar">
        <h2>Dashboard</h2>
        <div className="dash-toolbar-actions">
          <button className="ghost-btn" onClick={load}>Refresh</button>
          <button
            className="ghost-btn"
            onClick={() => {
              setStatus("");
              setCustomerId("");
              setQ("");
            }}
          >
            Reset
          </button>
        </div>
      </div>

      <div className="kpi-grid">
        <div className="kpi-card">
          <div className="kpi-label">Total Runs</div>
          <div className="kpi-value">{summary.total}</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-label">Running</div>
          <div className="kpi-value">{summary.running}</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-label">Failed</div>
          <div className="kpi-value">{summary.failed}</div>
        </div>
        <div className="kpi-card kpi-card-accent">
          <div className="kpi-label">Success Rate</div>
          <div className="kpi-value">{summary.successRate}%</div>
          <div className="kpi-sub">{summary.success} successful runs</div>
        </div>
      </div>

      <div className="filters-card">
        <select value={status} onChange={(e) => setStatus(e.target.value)} className="field">
          <option value="">All statuses</option>
          <option value="success">Success</option>
          <option value="failed">Failed</option>
          <option value="running">Running</option>
        </select>

        <input
          value={customerId}
          onChange={(e) => setCustomerId(e.target.value)}
          placeholder="Customer ID"
          className="field"
        />

        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search customer/campaign"
          className="field"
        />

        <button className="primary-btn" onClick={load}>Apply Filters</button>
      </div>

      <div className="table-card">
        <div className="table-header">
          <h3>Transaction Overview</h3>
          <span>{filtered.length} results</span>
        </div>

        <div className="table-wrap">
          <table className="runs-table">
            <thead>
              <tr>
                <th>Run At (Tehran)</th>
                <th>Customer</th>
                <th>Campaign</th>
                <th>Progress</th>
                <th>Status</th>
                <th>Run ID</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((r) => (
                <tr key={r.run_id}>
                  <td className="tehran-time">{formatTehran(r.started_at)}</td>
                  <td>{r.customer_name || "-"}</td>
                  <td>{r.campaign_name || "-"}</td>
                  <td className="mono-text">
                    {r.progress_current != null && r.progress_total != null
                      ? `${r.progress_current}/${r.progress_total} (${r.progress_pct ?? 0}%)`
                      : "-"}
                  </td>
                  <td>
                    <span className={`status-badge status-${r.status.toLowerCase()}`}>{r.status}</span>
                  </td>
                  <td className="mono-text">{r.run_id}</td>
                  <td>
                    <div className="row-actions">
                      {r.has_log && (
                        <Link to={`/runs/${r.run_id}/live-log`}>
                          <button className="ghost-btn">Live Log</button>
                        </Link>
                      )}
                      {r.has_log && (
                        <button
                          className="ghost-btn"
                          onClick={() => window.open(`${API_BASE}/runs/${r.run_id}/log/download`, "_blank")}
                        >
                          Download Log
                        </button>
                      )}
                      {r.has_result && (
                        <button
                          className="ghost-btn"
                          onClick={() => window.open(`${API_BASE}/runs/${r.run_id}/result/download`, "_blank")}
                        >
                          Send Result
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
              {filtered.length === 0 && (
                <tr>
                  <td colSpan={7} className="empty-cell">No runs found.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
