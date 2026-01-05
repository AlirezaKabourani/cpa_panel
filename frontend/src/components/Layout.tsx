import { Link, Outlet, useLocation } from "react-router-dom";

export default function Layout() {
  const loc = useLocation();
  const active = (path: string) => (loc.pathname === path ? { fontWeight: 700 } : undefined);

  return (
    <div style={{ display: "grid", gridTemplateColumns: "240px 1fr", height: "100vh" }}>
      <aside style={{ borderRight: "1px solid #eee", padding: 16 }}>
        <div style={{ fontWeight: 800, marginBottom: 12 }}>CPA_Panel</div>
        <nav style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <Link to="/" style={{ textDecoration: "none", color: "#111", ...active("/") }}>
            Dashboard
          </Link>
          <Link to="/campaign" style={{ textDecoration: "none", color: "#111", ...active("/campaign") }}>
            Create Campaign
          </Link>
        </nav>
        <div style={{ marginTop: 16, fontSize: 12, color: "#666" }}>
          Backend: localhost:8000
        </div>
      </aside>

      <main style={{ padding: 16, overflow: "auto" }}>
        <Outlet />
      </main>
    </div>
  );
}

