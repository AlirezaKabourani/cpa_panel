import { useEffect, useMemo, useState } from "react";
import { apiGet, apiPost, apiPostForm } from "../api/client";
import type { Customer, CustomerMedia, CustomerMessage } from "../api/types";
import DatePickerModule from "react-multi-date-picker";
import persian from "react-date-object/calendars/persian";
import persian_fa from "react-date-object/locales/persian_fa";
import DateObject from "react-date-object";
import { DateTime } from "luxon";

const DatePicker =
  (DatePickerModule as unknown as { default?: typeof DatePickerModule }).default ?? DatePickerModule;



export default function CampaignBuilder() {
  const [platform, setPlatform] = useState<"rubika" | "splus">("rubika");
  const theme = useMemo(
    () =>
      platform === "rubika"
        ? {
            pageBg:
              "linear-gradient(120deg, rgba(255,120,150,0.10), rgba(255,205,86,0.10), rgba(120,220,255,0.10), rgba(160,130,255,0.10))",
            cardBg: "#fffdfd",
            border: "#f2cde2",
            statusBg: "#fff7ff",
            statusBorder: "#efb6df",
          }
        : {
            pageBg: "linear-gradient(160deg, rgba(59,130,246,0.16), rgba(191,219,254,0.14), rgba(239,246,255,0.20))",
            cardBg: "#f8fbff",
            border: "#bfdbfe",
            statusBg: "#eff6ff",
            statusBorder: "#93c5fd",
          },
    [platform]
  );
  const cardStyle = { border: `1px solid ${theme.border}`, background: theme.cardBg, borderRadius: 12, padding: 12 };

  // Security: token is local-only, never stored
  const [token, setToken] = useState("");

  // Test number default
  const [testNumber, setTestNumber] = useState("989024004940");

  const [customers, setCustomers] = useState<Customer[]>([]);
  const [selectedCustomerId, setSelectedCustomerId] = useState<string>("");

  const selectedCustomer = useMemo(
    () => customers.find((c) => c.id === selectedCustomerId) || null,
    [customers, selectedCustomerId]
  );

  const [messages, setMessages] = useState<CustomerMessage[]>([]);
  const [media, setMedia] = useState<CustomerMedia[]>([]);
  const [selectedMessageId, setSelectedMessageId] = useState<string>("");
  const [messageText, setMessageText] = useState<string>("");

  // Save suggestion checkbox
  const [saveAsSuggestion, setSaveAsSuggestion] = useState(false);
  const [suggestionTitle, setSuggestionTitle] = useState("");

  const [status, setStatus] = useState<string>("");

  const [audienceFile, setAudienceFile] = useState<File | null>(null);
  const [snapshotId, setSnapshotId] = useState<string>("");
  const [audienceNotes, setAudienceNotes] = useState<string[]>([]);
  const [audiencePreview, setAudiencePreview] = useState<any[]>([]);
  const [audienceColumns, setAudienceColumns] = useState<string[]>([]);
  const [audienceRowCount, setAudienceRowCount] = useState<number>(0);

  const [selectedFileId, setSelectedFileId] = useState<string>("");
  const [createdCampaignId, setCreatedCampaignId] = useState<string>("");

  const [lastRunId, setLastRunId] = useState<string>("");
  const [lastRunLog, setLastRunLog] = useState<string>("");

  const [mediaFile, setMediaFile] = useState<File | null>(null);
  const [mediaType, setMediaType] = useState<"Image" | "Video">("Image");

  const [scheduleAt, setScheduleAt] = useState<DateObject | null>(null);
  const [scheduledRuns, setScheduledRuns] = useState<any[]>([]);
  const [campaignName, setCampaignName] = useState<string>("");
  const [scheduleTime, setScheduleTime] = useState<string>("13:30");




  async function uploadAudience() {
  if (!audienceFile) {
    setStatus("Select a .xlsx or .csv file first.");
    return;
  }
  setStatus("Uploading audience...");
  try {
      const fd = new FormData();
      fd.append("file", audienceFile);
      const res = await apiPostForm<{
        snapshot_id: string;
        row_count: number;
        columns: string[];
        preview: any[];
        notes: string[];
      }>("/audience/upload", fd);

      setSnapshotId(res.snapshot_id);
      setAudienceRowCount(res.row_count);
      setAudienceColumns(res.columns);
      setAudiencePreview(res.preview);
      setAudienceNotes(res.notes || []);
      setStatus(`Audience uploaded. snapshot_id=${res.snapshot_id} rows=${res.row_count}`);
    } catch (e: any) {
      setStatus(`Upload failed: ${e.message || e}`);
    }
  }

  async function uploadMedia() {
    if (!selectedCustomer) return setStatus("Select a customer first.");
    if (!token.trim()) return setStatus("Token is required (not saved).");
    if (!mediaFile) return setStatus("Choose a media file first.");

    setStatus(`Uploading media to ${platform === "rubika" ? "Rubika" : "SPlus"}...`);
    try {
      const fd = new FormData();
      fd.append("token", token);
      fd.append("file_type", mediaType);
      fd.append("platform", platform);
      fd.append("file", mediaFile);

      const res = await apiPostForm<{ media_id: string; file_id: string }>(
        `/customers/${selectedCustomer.id}/media/upload`,
        fd
      );

      setStatus(`Media uploaded. file_id=${res.file_id}`);
      setMediaFile(null);

      // refresh media list
      await loadCustomerExtras(selectedCustomer.id);
    } catch (e: any) {
      setStatus(`Media upload failed: ${e.message || e}`);
    }
  }


  async function createCampaign() {
  setStatus("");

  if (!selectedCustomer) {
    setStatus("Select a customer first.");
    return;
  }
  if (!snapshotId) {
    setStatus("Upload an audience file first (snapshot_id missing).");
    return;
  }
  if (!messageText.trim()) {
    setStatus("Message is empty.");
    return;
  }

    try {
      const res = await apiPost<{ campaign_id: string; status: string }>("/campaigns", {
        name: campaignName.trim(),
        platform,
        customer_id: selectedCustomer.id,
        audience_snapshot_id: snapshotId,
        selected_file_id: selectedFileId || null,
        message_text: messageText,
        test_number: testNumber,
      });

      setCreatedCampaignId(res.campaign_id);
      setStatus(`Campaign saved. id=${res.campaign_id} status=${res.status}`);
    } catch (e: any) {
      setStatus(`Failed to create campaign: ${e.message || e}`);
    }
  }

  async function loadCustomers() {
    const list = await apiGet<Customer[]>(`/customers?platform=${platform}`);
    setCustomers(list);
    if (!list.some((x) => x.id === selectedCustomerId)) {
      setSelectedCustomerId(list.length ? list[0].id : "");
    }
  }

  async function loadCustomerExtras(customerId: string) {
    const [m, med] = await Promise.all([
      apiGet<CustomerMessage[]>(`/customers/${customerId}/messages`),
      apiGet<CustomerMedia[]>(`/customers/${customerId}/media?platform=${platform}`),
    ]);
    setMessages(m);
    setMedia(med);

    // Reset selections
    setSelectedMessageId("");
    setMessageText("");
    setSelectedFileId("");
    setCreatedCampaignId("");
  }

  async function sendTest() {
    if (!createdCampaignId) return setStatus("Create campaign first.");
    if (!token.trim()) return setStatus("Token is required (not saved).");

    setStatus("Sending test...");
    setLastRunLog("");

    try {
      const res = await apiPost<{ run_id: string; status: string; log_url?: string }>(
        `/campaigns/${createdCampaignId}/send-test`,
        { token, test_number: testNumber }
      );

      setLastRunId(res.run_id);
      setStatus(`Test finished. run_id=${res.run_id} status=${res.status}`);
      await fetchRunLog(res.run_id);
    } catch (e: any) {
      setStatus(`Test failed: ${e.message || e}`);
    }
  }


  async function runNow() {
    if (!createdCampaignId) return setStatus("Create campaign first.");
    if (!token.trim()) return setStatus("Token is required (not saved).");

    setStatus("Running campaign now...");
    setLastRunLog("");

    try {
      const res = await apiPost<{ run_id: string; status: string; log_url?: string }>(
        `/campaigns/${createdCampaignId}/run-now`,
        { token }
      );

      setLastRunId(res.run_id);
      setStatus(`Run finished. run_id=${res.run_id} status=${res.status}`);
      await fetchRunLog(res.run_id);
    } catch (e: any) {
      setStatus(`Run failed: ${e.message || e}`);
    }
  }
  



  useEffect(() => {
    loadCustomers().catch((e) => setStatus(`Error: ${String(e.message || e)}`));
    // eslint-disable-next-line react-hooks/exhaustive-deps
    refreshScheduledRuns();
  }, []);

  useEffect(() => {
    loadCustomers().catch((e) => setStatus(`Error: ${String(e.message || e)}`));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [platform]);

  useEffect(() => {
    if (!selectedCustomerId) return;
    loadCustomerExtras(selectedCustomerId).catch((e) => setStatus(`Error: ${String(e.message || e)}`));
  }, [selectedCustomerId, platform]);

  useEffect(() => {
    if (platform !== "splus") return;
    setToken(selectedCustomer?.default_splus_token || "");
  }, [platform, selectedCustomer]);

  useEffect(() => {
    const msg = messages.find((x) => x.id === selectedMessageId);
    if (msg) setMessageText(msg.text_template);
  }, [selectedMessageId, messages]);

  async function saveSuggestion() {
    if (!selectedCustomer) {
      setStatus("Select a customer first.");
      return;
    }
    if (!messageText.trim()) {
      setStatus("Message is empty.");
      return;
    }
    try {
      await apiPost(`/customers/${selectedCustomer.id}/messages`, {
        title: suggestionTitle.trim() || null,
        text_template: messageText,
      });
      setSaveAsSuggestion(false);
      setSuggestionTitle("");
      await loadCustomerExtras(selectedCustomer.id);
      setStatus("Saved as suggestion.");
    } catch (e: any) {
      setStatus(`Error saving suggestion: ${e.message || e}`);
    }
  }

  async function fetchRunLog(runId: string) {
  try {
    const res = await apiGet<{ log: string }>(`/runs/${runId}/log`);
    setLastRunLog(res.log);
  } catch (e: any) {
    setLastRunLog(`(Could not load log) ${e.message || e}`);
  }
}

function tehranPickerToUtcIso(dateObj: DateObject, hhmm: string): string {
    const [hhStr, mmStr] = (hhmm || "00:00").split(":");
    const hh = Number(hhStr) || 0;
    const mm = Number(mmStr) || 0;

    // Interpret selected date in Tehran timezone, then set time and convert to UTC ISO
    const base = DateTime.fromJSDate(dateObj.toDate(), { zone: "Asia/Tehran" });
    return base
      .set({ hour: hh, minute: mm, second: 0, millisecond: 0 })
      .toUTC()
      .toISO()!;
  }


  function formatTehran(isoUtc: string): string {
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


  async function refreshScheduledRuns() {
    const rows = await apiGet<any[]>("/scheduled-runs");
    setScheduledRuns(rows);
  }

  async function scheduleCampaign() {
    if (!createdCampaignId) return setStatus("Create campaign first.");
    if (!scheduleAt) return setStatus("Select date/time first.");
    if (!token.trim()) return setStatus("Token is required for scheduling.");

    const run_at = tehranPickerToUtcIso(scheduleAt, scheduleTime);

    try {
      const res = await apiPost<{ scheduled_run_id: string; status: string }>(
        `/campaigns/${createdCampaignId}/schedule`,
        { run_at, token }
      );
      setStatus(`Scheduled. scheduled_run_id=${res.scheduled_run_id} status=${res.status}`);
      await refreshScheduledRuns();
    } catch (e: any) {
      setStatus(`Schedule failed: ${e.message || e}`);
    }
  }


  async function runScheduledNowWithToken(id: string) {
    if (!token.trim()) return setStatus("Token is required (not saved).");

    try {
      await apiPost(`/scheduled-runs/${id}/run-now-with-token`, { token });
      setStatus("Token provided. It will execute shortly.");
      await refreshScheduledRuns();
    } catch (e: any) {
      setStatus(`Failed: ${e.message || e}`);
    }
  }

  async function cancelScheduledRun(id: string) {
    try {
      await apiPost(`/scheduled-runs/${id}/cancel`, {});
      setStatus("Canceled.");
      await refreshScheduledRuns();
    } catch (e: any) {
      setStatus(`Cancel failed: ${e.message || e}`);
    }
  }



  return (
    <div style={{ display: "grid", gap: 16, background: theme.pageBg, padding: 14, borderRadius: 14 }}>
      <div style={cardStyle}>
        <h3 style={{ marginTop: 0, marginBottom: 8 }}>Social Media</h3>
        <select
          value={platform}
          onChange={(e) => setPlatform(e.target.value as "rubika" | "splus")}
          style={{ padding: 8, borderRadius: 8, minWidth: 220 }}
        >
          <option value="rubika">Rubika</option>
          <option value="splus">SPlus</option>
        </select>
      </div>

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h2 style={{ margin: 0 }}>Create Campaign (Step 1)</h2>
      </div>

      {status && (
        <div style={{ padding: 10, background: theme.statusBg, border: `1px solid ${theme.statusBorder}`, borderRadius: 8 }}>
          {status}
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        {/* Customer + token */}
        <div style={cardStyle}>
          <h3 style={{ marginTop: 0 }}>Customer + Security</h3>

          <div style={{ display: "grid", gap: 8 }}>
            <label>
              Customer
              <div>
                <select
                  value={selectedCustomerId}
                  onChange={(e) => setSelectedCustomerId(e.target.value)}
                  style={{ width: "100%", padding: 8, borderRadius: 8 }}
                >
                  {customers.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                    </option>
                  ))}
                </select>
              </div>
            </label>

            <label>
              {platform === "rubika" ? "Rubika Token (not saved)" : "SPlus Bot ID (not saved)"}
              <input
                type="password"
                value={token}
                onChange={(e) => setToken(e.target.value)}
                placeholder={platform === "rubika" ? "Paste token each run..." : "Paste SPlus bot_id each run..."}
                style={{ width: "100%", padding: 8, borderRadius: 8 }}
              />
            </label>

            <label>
              Test number
              <input
                value={testNumber}
                onChange={(e) => setTestNumber(e.target.value)}
                style={{ width: "100%", padding: 8, borderRadius: 8 }}
              />
            </label>

            <div style={{ fontSize: 12, color: "#666" }}>
              Token is never stored and is required for send test / run now / schedule.
            </div>
          </div>
        </div>

        {/* Media list */}
        {media.length > 0 && (
          <div style={{ marginTop: 10 }}>
            <label style={{ fontSize: 13 }}>
              Select media (file_id)
              <select
                value={selectedFileId}
                onChange={(e) => setSelectedFileId(e.target.value)}
                style={{ width: "100%", padding: 8, borderRadius: 8, marginTop: 6 }}
              >
                <option value="">(No media)</option>
                {media.map((m) => (
                  <option key={m.id} value={m.file_id}>
                    {m.file_id}{m.file_name ? ` - ${m.file_name}` : ""}
                  </option>
                ))}
              </select>
            </label>
          </div>
        )}

        <div style={cardStyle}>
          <h3 style={{ marginTop: 0 }}>Customer Media (file_id)</h3>
          <div style={{ marginTop: 12, display: "grid", gap: 8 }}>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
              <select
                value={mediaType}
                onChange={(e) => setMediaType(e.target.value as "Image" | "Video")}
                style={{ padding: 8, borderRadius: 8 }}
              >
                <option value="Image">Image</option>
                <option value="Video">Video</option>
              </select>

              <input
                type="file"
                accept={mediaType === "Image" ? "image/*" : "video/*"}
                onChange={(e) => setMediaFile(e.target.files?.[0] || null)}
              />

              <button onClick={uploadMedia} disabled={!selectedCustomer || !mediaFile || !token.trim()}>
                Upload media
              </button>
            </div>

          </div>

          
          {!selectedCustomer ? (
            <div style={{ color: "#666" }}>Select a customer.</div>
          ) : media.length === 0 ? (
            <div style={{ color: "#666" }} />
          ) : (
            <ul style={{ margin: 0, paddingLeft: 18 }}>
              {media.map((m) => (
                <li key={m.id}>
                  <span style={{ fontFamily: "monospace" }}>{m.file_id}</span>
                  {m.file_name ? <span> - {m.file_name}</span> : null}
                  {m.file_type ? <span style={{ color: "#666" }}> ({m.file_type})</span> : null}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      {/* Audience upload */}
<div style={cardStyle}>
  <h3 style={{ marginTop: 0 }}>Audience (Upload XLSX/CSV)</h3>

  <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
    <input
      type="file"
      accept=".xlsx,.xls,.csv"
      onChange={(e) => setAudienceFile(e.target.files?.[0] || null)}
    />
    <button onClick={uploadAudience} disabled={!audienceFile}>
      Upload & Preview
    </button>

    {snapshotId && (
      <div style={{ fontSize: 12, color: "#666" }}>
        Snapshot: <span style={{ fontFamily: "monospace" }}>{snapshotId}</span> - Rows: {audienceRowCount}
      </div>
    )}
  </div>

  {audienceNotes.length > 0 && (
    <ul style={{ marginTop: 10, color: "#666" }}>
      {audienceNotes.map((n, idx) => (
        <li key={idx}>{n}</li>
      ))}
    </ul>
  )}

  {audiencePreview.length > 0 && (
    <div style={{ marginTop: 12, overflowX: "auto" }}>
      <div style={{ fontSize: 12, color: "#666", marginBottom: 6 }}>
        Preview (first {audiencePreview.length} rows)
      </div>

      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead>
          <tr>
            {audienceColumns.slice(0, 6).map((c) => (
              <th key={c} align="left" style={{ borderBottom: "1px solid #eee", padding: "6px 0" }}>
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {audiencePreview.map((row, i) => (
            <tr key={i} style={{ borderBottom: "1px solid #f4f4f4" }}>
              {audienceColumns.slice(0, 6).map((c) => (
                <td key={c} style={{ padding: "6px 0", fontFamily: c === "phone_number" ? "monospace" : "inherit" }}>
                  {String(row[c] ?? "")}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>

      <div style={{ marginTop: 8, fontSize: 12, color: "#666" }}>
        (Showing up to 10 columns for simplicity.)
      </div>
    </div>
  )}
</div>


      {/* Message suggestions + editor */}
      <div style={cardStyle}>
        <h3 style={{ marginTop: 0 }}>Message</h3>

        <div style={{ display: "grid", gridTemplateColumns: "320px 1fr", gap: 12 }}>
          <div style={{ borderRight: "1px solid #f0f0f0", paddingRight: 12 }}>
            <div style={{ fontWeight: 700, marginBottom: 8 }}>Suggested messages</div>

            {!selectedCustomer ? (
              <div style={{ color: "#666" }}>Select a customer.</div>
            ) : messages.length === 0 ? (
              <div style={{ color: "#666" }}>No suggestions yet. Write one and save it.</div>
            ) : (
              <div style={{ display: "grid", gap: 8 }}>
                {messages.map((m) => (
                  <label key={m.id} style={{ display: "flex", gap: 8, alignItems: "flex-start" }}>
                    <input
                      type="radio"
                      name="suggested"
                      checked={selectedMessageId === m.id}
                      onChange={() => setSelectedMessageId(m.id)}
                      style={{ marginTop: 3 }}
                    />
                    <div>
                      <div style={{ fontSize: 13, fontWeight: 600 }}>
                        {m.title ? m.title : "Untitled"}
                      </div>
                      <div style={{ fontSize: 12, color: "#666" }}>
                        {m.text_template.slice(0, 70)}
                        {m.text_template.length > 70 ? "..." : ""}
                      </div>
                    </div>
                  </label>
                ))}
              </div>
            )}
          </div>

          <div>
            <textarea
              value={messageText}
              onChange={(e) => setMessageText(e.target.value)}
              placeholder="Write your message text_template here. Use %s for link placeholder."
              style={{ width: "100%", minHeight: 220, padding: 10, borderRadius: 8, fontFamily: "inherit" }}
            />
            {!messageText.includes("%s") && (
              <div style={{ marginTop: 8, color: "#b45309", fontSize: 13 }}>
                Warning: your message does not include <code>%s</code>. The selected platform needs it to inject the link.
              </div>
            )}

            <div style={{ display: "flex", justifyContent: "space-between", marginTop: 10, alignItems: "center" }}>
              <label style={{ display: "flex", gap: 8, alignItems: "center" }}>
                <input
                  type="checkbox"
                  checked={saveAsSuggestion}
                  onChange={(e) => setSaveAsSuggestion(e.target.checked)}
                />
                Save this message as a suggestion for this customer
              </label>

              <button onClick={saveSuggestion} disabled={!saveAsSuggestion}>
                Save suggestion
              </button>
            </div>

            {saveAsSuggestion && (
              <div style={{ marginTop: 10 }}>
                <input
                  value={suggestionTitle}
                  onChange={(e) => setSuggestionTitle(e.target.value)}
                  placeholder="Optional title (e.g., 'TechnoPay reminder')"
                  style={{ width: "100%", padding: 8, borderRadius: 8 }}
                />
              </div>
            )}
          </div>
        </div>
      </div>


      {/* Save campaign */}
      <div style={cardStyle}>
        <h3 style={{ marginTop: 0 }}>Save Campaign</h3>

        <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center" }}>
          <input
            value={campaignName}
            onChange={(e) => setCampaignName(e.target.value)}
            placeholder='Campaign name (e.g., "sahel_S001")'
            style={{ padding: 8, borderRadius: 8, minWidth: 260 }}
          />
          <button onClick={createCampaign} disabled={!selectedCustomer || !snapshotId || !messageText.trim() || !messageText.includes("%s")}>
            Create Campaign (Save Draft)
          </button>

          {createdCampaignId && (
            <div style={{ fontSize: 12, color: "#666" }}>
              Campaign ID: <span style={{ fontFamily: "monospace" }}>{createdCampaignId}</span>
            </div>
          )}
        </div>

        <div style={{ marginTop: 8, fontSize: 12, color: "#666" }}>
          Next step: Send test / Run now / Schedule (will use this saved campaign).
        </div>
      </div>
      <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center" }}>

        <button onClick={sendTest} disabled={!createdCampaignId}>
          Send Test
        </button>

        <button onClick={runNow} disabled={!createdCampaignId}>
          Run Now
        </button>

        {createdCampaignId && (
          <div style={{ fontSize: 12, color: "#666" }}>
            Campaign ID: <span style={{ fontFamily: "monospace" }}>{createdCampaignId}</span>
          </div>
        )}
      </div>

      {/* Scheduler */}
      <div style={cardStyle}>
        <h3 style={{ marginTop: 0 }}>Scheduler</h3>

        <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center" }}>
          <DatePicker
            value={scheduleAt}
            onChange={(v) => setScheduleAt(v as DateObject)}
            calendar={persian}
            locale={persian_fa}
            format="YYYY/MM/DD"
            inputClass="picker-input"
            style={{ padding: 8, borderRadius: 8 }}
          />

          <input
            type="time"
            value={scheduleTime}
            onChange={(e) => setScheduleTime(e.target.value)}
            style={{ padding: 8, borderRadius: 8, border: "1px solid #ddd" }}
          />


          <button onClick={scheduleCampaign} disabled={!createdCampaignId || !scheduleAt}>
            Schedule
          </button>

          <button onClick={refreshScheduledRuns}>
            Refresh list
          </button>
        </div>


        {/* List */}
        <div style={{ marginTop: 12, overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr>
                <th align="left" style={{ borderBottom: "1px solid #eee", padding: "6px 0" }}>Run At (Tehran)</th>
                <th align="left" style={{ borderBottom: "1px solid #eee", padding: "6px 0" }}>Customer</th>
                <th align="left" style={{ borderBottom: "1px solid #eee", padding: "6px 0" }}>Campaign Name</th>                
                <th align="left" style={{ borderBottom: "1px solid #eee", padding: "6px 0" }}>Status</th>
                <th align="left" style={{ borderBottom: "1px solid #eee", padding: "6px 0" }}>Campaign ID</th>
                <th align="left" style={{ borderBottom: "1px solid #eee", padding: "6px 0" }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {scheduledRuns.map((r) => (
                <tr key={r.id} style={{ borderBottom: "1px solid #f4f4f4" }}>
                  <td style={{ padding: "6px 0", fontFamily: "monospace", fontSize: 12 }}>{formatTehran(r.run_at)}</td>
                  <td style={{ padding: "6px 0" }}>{r.customer_name || "-"}</td>
                  <td style={{ padding: "6px 0" }}>{r.campaign_name || "-"}</td>
                  <td style={{ padding: "6px 0" }}>
                    {r.status}{r.has_token ? " [locked]" : ""}
                  </td>
                  <td style={{ padding: "6px 0", fontFamily: "monospace", fontSize: 12 }}>{r.campaign_id}</td>
                  <td style={{ padding: "6px 0", display: "flex", gap: 8, flexWrap: "wrap" }}>
                    {r.status === "waiting_token" && (
                      <button onClick={() => runScheduledNowWithToken(r.id)}>
                        Run now with token
                      </button>
                    )}
                    {["scheduled", "waiting_token"].includes(r.status) && (
                      <button onClick={() => cancelScheduledRun(r.id)}>
                        Cancel
                      </button>
                    )}
                    {r.last_run_id && (
                      <button onClick={() => window.open(`http://127.0.0.1:8000/api/runs/${r.last_run_id}/log/download`, "_blank")}>
                        Download log
                      </button>
                    )}
                    {r.last_run_id && (
                      <button onClick={() => window.open(`http://127.0.0.1:8000/api/runs/${r.last_run_id}/result/download`, "_blank")}>
                        Download Result
                      </button>
                    )}

                  </td>
                </tr>
              ))}
              {scheduledRuns.length === 0 && (
                <tr><td colSpan={4} style={{ padding: "10px 0", color: "#666" }}>No scheduled runs.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>



      {/* Run Log Viewer */}
      <div style={cardStyle}>
        <h3 style={{ marginTop: 0 }}>Last Run Log</h3>

        {!lastRunId ? (
          <div style={{ color: "#666" }}>No run yet. Use "Send Test" or "Run Now".</div>
        ) : (
          <div style={{ display: "grid", gap: 10 }}>
            <div style={{ fontSize: 12, color: "#666" }}>
              Run ID: <span style={{ fontFamily: "monospace" }}>{lastRunId}</span>
              <button onClick={() => fetchRunLog(lastRunId)} style={{ marginLeft: 10 }}>
                Refresh log
              </button>
            </div>

            <textarea
              readOnly
              value={lastRunLog}
              style={{
                width: "100%",
                minHeight: 220,
                padding: 10,
                borderRadius: 8,
                fontFamily: "ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
                fontSize: 12,
                whiteSpace: "pre",
              }}
            />
          </div>
        )}
      </div>

    </div>
  );
}

