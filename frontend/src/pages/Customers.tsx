import { useEffect, useMemo, useState } from "react";
import { API_BASE, apiDelete, apiGet, apiPost, apiPut } from "../api/client";
import type { Customer, CustomerMedia, CustomerMessage } from "../api/types";

type CampaignRow = {
  id: string;
  name?: string | null;
  platform?: "rubika" | "splus" | string;
  status?: string;
  created_at?: string;
  customer_id: string;
};

type RunRow = {
  run_id: string;
  campaign_id: string;
  campaign_name?: string | null;
  customer_id: string;
  customer_name?: string | null;
  status: string;
  started_at?: string | null;
  finished_at?: string | null;
  has_log: boolean;
  has_result: boolean;
};

function Modal(props: { open: boolean; title: string; onClose: () => void; children: React.ReactNode }) {
  if (!props.open) return null;
  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(0,0,0,0.35)",
        display: "grid",
        placeItems: "center",
        zIndex: 1000,
      }}
      onMouseDown={props.onClose}
    >
      <div
        style={{ width: 520, maxWidth: "95vw", background: "#fff", borderRadius: 12, padding: 16 }}
        onMouseDown={(e) => e.stopPropagation()}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h3 style={{ margin: 0 }}>{props.title}</h3>
          <button onClick={props.onClose}>×</button>
        </div>
        <div style={{ marginTop: 12 }}>{props.children}</div>
      </div>
    </div>
  );
}

export default function CustomersPage() {
  const [status, setStatus] = useState("");
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [selectedId, setSelectedId] = useState("");

  const [createOpen, setCreateOpen] = useState(false);
  const [newName, setNewName] = useState("");
  const [newServiceId, setNewServiceId] = useState("");
  const [newSplusToken, setNewSplusToken] = useState("");

  const [name, setName] = useState("");
  const [serviceId, setServiceId] = useState("");
  const [splusToken, setSplusToken] = useState("");

  const [messages, setMessages] = useState<CustomerMessage[]>([]);
  const [mediaRubika, setMediaRubika] = useState<CustomerMedia[]>([]);
  const [mediaSplus, setMediaSplus] = useState<CustomerMedia[]>([]);
  const [campaigns, setCampaigns] = useState<CampaignRow[]>([]);
  const [runs, setRuns] = useState<RunRow[]>([]);
  const [editingMsgId, setEditingMsgId] = useState("");
  const [editMsgTitle, setEditMsgTitle] = useState("");
  const [editMsgText, setEditMsgText] = useState("");

  const selected = useMemo(() => customers.find((c) => c.id === selectedId) || null, [customers, selectedId]);

  async function loadCustomers() {
    const rows = await apiGet<Customer[]>("/customers");
    setCustomers(rows);
    if (!rows.some((x) => x.id === selectedId)) setSelectedId(rows[0]?.id || "");
  }

  async function loadDetails(customerId: string) {
    const [m, rub, sps, allCampaigns, runsByCustomer] = await Promise.all([
      apiGet<CustomerMessage[]>(`/customers/${customerId}/messages`),
      apiGet<CustomerMedia[]>(`/customers/${customerId}/media?platform=rubika`),
      apiGet<CustomerMedia[]>(`/customers/${customerId}/media?platform=splus`),
      apiGet<CampaignRow[]>("/campaigns"),
      apiGet<RunRow[]>(`/dashboard/runs?customer_id=${customerId}&limit=500`),
    ]);
    setMessages(m);
    setMediaRubika(rub);
    setMediaSplus(sps);
    setCampaigns(allCampaigns.filter((x) => x.customer_id === customerId));
    setRuns(runsByCustomer);
  }

  useEffect(() => {
    loadCustomers().catch((e) => setStatus(String(e?.message || e)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!selectedId) return;
    loadDetails(selectedId).catch((e) => setStatus(String(e?.message || e)));
  }, [selectedId]);

  useEffect(() => {
    if (!selected) return;
    setName(selected.name || "");
    setServiceId(selected.service_id || "");
    setSplusToken(selected.default_splus_token || "");
  }, [selected]);

  async function onCreateCustomer() {
    if (!newName.trim()) return setStatus("name is required");
    try {
      await apiPost("/customers", {
        name: newName.trim(),
        service_id: newServiceId.trim() || "",
        default_splus_token: newSplusToken.trim() || null,
      });
      setStatus("Customer added.");
      setCreateOpen(false);
      setNewName("");
      setNewServiceId("");
      setNewSplusToken("");
      await loadCustomers();
    } catch (e: any) {
      setStatus(String(e?.message || e));
    }
  }

  async function onSaveCustomer() {
    if (!selected) return;
    if (!name.trim()) return setStatus("name is required");
    try {
      await apiPut(`/customers/${selected.id}`, {
        name: name.trim(),
        service_id: serviceId.trim() || "",
        default_splus_token: splusToken.trim() || null,
      });
      setStatus("Customer updated.");
      await loadCustomers();
      await loadDetails(selected.id);
    } catch (e: any) {
      setStatus(String(e?.message || e));
    }
  }

  function startEditMessage(m: CustomerMessage) {
    setEditingMsgId(m.id);
    setEditMsgTitle(m.title || "");
    setEditMsgText(m.text_template || "");
  }

  async function saveMessageEdit() {
    if (!selected || !editingMsgId) return;
    if (!editMsgText.trim()) return setStatus("Message text cannot be empty.");
    try {
      await apiPut(`/customers/${selected.id}/messages/${editingMsgId}`, {
        title: editMsgTitle.trim() || null,
        text_template: editMsgText,
      });
      setEditingMsgId("");
      setStatus("Message updated.");
      await loadDetails(selected.id);
    } catch (e: any) {
      setStatus(String(e?.message || e));
    }
  }

  async function removeMessage(messageId: string) {
    if (!selected) return;
    try {
      await apiDelete(`/customers/${selected.id}/messages/${messageId}`);
      setStatus("Message removed.");
      await loadDetails(selected.id);
    } catch (e: any) {
      setStatus(String(e?.message || e));
    }
  }

  return (
    <div style={{ display: "grid", gap: 14 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h2 style={{ margin: 0 }}>Customers</h2>
        <button onClick={() => setCreateOpen(true)}>+ New Customer</button>
      </div>
      {status && <div style={{ padding: 10, border: "1px solid #e5e7eb", borderRadius: 8 }}>{status}</div>}

      <div style={{ display: "grid", gridTemplateColumns: "320px 1fr", gap: 12 }}>
        <div style={{ border: "1px solid #eee", borderRadius: 12, padding: 12 }}>
          <div style={{ fontWeight: 700, marginBottom: 8 }}>Customer list</div>
          <select
            value={selectedId}
            onChange={(e) => setSelectedId(e.target.value)}
            style={{ width: "100%", padding: 8, borderRadius: 8, marginBottom: 10 }}
          >
            {customers.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
          <div style={{ display: "grid", gap: 8 }}>
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Customer name" style={{ padding: 8, borderRadius: 8 }} />
            <input value={serviceId} onChange={(e) => setServiceId(e.target.value)} placeholder="Rubika service_id (optional)" style={{ padding: 8, borderRadius: 8 }} />
            <input value={splusToken} onChange={(e) => setSplusToken(e.target.value)} placeholder="SPlus default token (optional)" style={{ padding: 8, borderRadius: 8 }} />
            <div style={{ display: "flex", gap: 8 }}>
              <button onClick={onSaveCustomer} disabled={!selected}>Save Edit</button>
            </div>
          </div>
        </div>

        <div style={{ display: "grid", gap: 12 }}>
          <div style={{ border: "1px solid #eee", borderRadius: 12, padding: 12 }}>
            <h3 style={{ marginTop: 0 }}>Suggested messages</h3>
            {messages.length === 0 ? (
              <div style={{ color: "#666" }}>No messages.</div>
            ) : (
              <div style={{ display: "grid", gap: 8 }}>
                {messages.map((m) => (
                  <div key={m.id} style={{ border: "1px solid #f0f0f0", borderRadius: 8, padding: 8 }}>
                    {editingMsgId === m.id ? (
                      <div style={{ display: "grid", gap: 8 }}>
                        <input value={editMsgTitle} onChange={(e) => setEditMsgTitle(e.target.value)} placeholder="Title" style={{ padding: 8, borderRadius: 8 }} />
                        <textarea value={editMsgText} onChange={(e) => setEditMsgText(e.target.value)} style={{ minHeight: 90, padding: 8, borderRadius: 8 }} />
                        <div style={{ display: "flex", gap: 8 }}>
                          <button onClick={saveMessageEdit}>Save</button>
                          <button onClick={() => setEditingMsgId("")}>Cancel</button>
                        </div>
                      </div>
                    ) : (
                      <div>
                        <div style={{ fontWeight: 700 }}>{m.title || "Untitled"}</div>
                        <div style={{ whiteSpace: "pre-wrap", fontSize: 13 }}>{m.text_template}</div>
                        <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
                          <button onClick={() => startEditMessage(m)}>Edit</button>
                          <button onClick={() => removeMessage(m.id)}>Remove</button>
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

          <div style={{ border: "1px solid #eee", borderRadius: 12, padding: 12 }}>
            <h3 style={{ marginTop: 0 }}>Uploaded media</h3>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
              <div>
                <div style={{ fontWeight: 700, marginBottom: 6 }}>Rubika</div>
                {mediaRubika.length === 0 ? <div style={{ color: "#666" }}>No media.</div> : (
                  <ul style={{ margin: 0, paddingLeft: 18 }}>
                    {mediaRubika.map((m) => <li key={m.id}><code>{m.file_id}</code></li>)}
                  </ul>
                )}
              </div>
              <div>
                <div style={{ fontWeight: 700, marginBottom: 6 }}>SPlus</div>
                {mediaSplus.length === 0 ? <div style={{ color: "#666" }}>No media.</div> : (
                  <ul style={{ margin: 0, paddingLeft: 18 }}>
                    {mediaSplus.map((m) => <li key={m.id}><code>{m.file_id}</code></li>)}
                  </ul>
                )}
              </div>
            </div>
          </div>

          <div style={{ border: "1px solid #eee", borderRadius: 12, padding: 12 }}>
            <h3 style={{ marginTop: 0 }}>Campaigns</h3>
            {campaigns.length === 0 ? <div style={{ color: "#666" }}>No campaigns.</div> : (
              <table style={{ width: "100%", borderCollapse: "collapse" }}>
                <thead>
                  <tr>
                    <th align="left">Name</th>
                    <th align="left">Platform</th>
                    <th align="left">Status</th>
                    <th align="left">Created</th>
                  </tr>
                </thead>
                <tbody>
                  {campaigns.map((c) => (
                    <tr key={c.id} style={{ borderTop: "1px solid #f4f4f4" }}>
                      <td>{c.name || "-"}</td>
                      <td>{c.platform || "-"}</td>
                      <td>{c.status || "-"}</td>
                      <td><code>{c.created_at || "-"}</code></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          <div style={{ border: "1px solid #eee", borderRadius: 12, padding: 12 }}>
            <h3 style={{ marginTop: 0 }}>Executed runs</h3>
            {runs.length === 0 ? <div style={{ color: "#666" }}>No runs.</div> : (
              <table style={{ width: "100%", borderCollapse: "collapse" }}>
                <thead>
                  <tr>
                    <th align="left">Run time</th>
                    <th align="left">Campaign</th>
                    <th align="left">Status</th>
                    <th align="left">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {runs.map((r) => (
                    <tr key={r.run_id} style={{ borderTop: "1px solid #f4f4f4" }}>
                      <td><code>{r.started_at || "-"}</code></td>
                      <td>{r.campaign_name || "-"}</td>
                      <td>{r.status}</td>
                      <td style={{ display: "flex", gap: 6 }}>
                        {r.has_log && <button onClick={() => window.open(`${API_BASE}/runs/${r.run_id}/log/download`, "_blank")}>Log</button>}
                        {r.has_result && <button onClick={() => window.open(`${API_BASE}/runs/${r.run_id}/result/download`, "_blank")}>Result</button>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      </div>

      <Modal open={createOpen} title="New Customer" onClose={() => setCreateOpen(false)}>
        <div style={{ display: "grid", gap: 10 }}>
          <label>
            Name
            <input
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="Customer name"
              style={{ width: "100%", padding: 8, borderRadius: 8 }}
            />
          </label>
          <label>
            Rubika service_id (if available)
            <input
              value={newServiceId}
              onChange={(e) => setNewServiceId(e.target.value)}
              placeholder="24-char Rubika service_id"
              style={{ width: "100%", padding: 8, borderRadius: 8 }}
            />
          </label>
          <label>
            SPlus default token (if available)
            <input
              value={newSplusToken}
              onChange={(e) => setNewSplusToken(e.target.value)}
              placeholder="SPlus token"
              style={{ width: "100%", padding: 8, borderRadius: 8 }}
            />
          </label>
          <div style={{ display: "flex", justifyContent: "flex-end", gap: 8 }}>
            <button onClick={() => setCreateOpen(false)}>Cancel</button>
            <button onClick={onCreateCustomer}>Create</button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
