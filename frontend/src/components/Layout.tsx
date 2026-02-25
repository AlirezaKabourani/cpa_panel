import { NavLink, Outlet } from "react-router-dom";
import "./Layout.css";

export default function Layout() {
  return (
    <div className="app-shell">
      <aside className="side-panel">
        <div className="brand-header">
          <div className="brand-row">
            <img src="/CPA_PANEL_LOGO.png" alt="CPA Panel logo" className="brand-logo" />
            <div className="brand-title">CPA Panel</div>
          </div>
        </div>

        <div className="side-menu-area">
          <nav className="side-nav side-nav-primary">
            <NavLink to="/" end className={({ isActive }) => `side-link ${isActive ? "active" : ""}`}>
              Dashboard
            </NavLink>
          </nav>

          <div className="side-divider" />
          <div className="side-section-title">Management</div>
          <nav className="side-nav">
            <NavLink to="/campaign" className={({ isActive }) => `side-link ${isActive ? "active" : ""}`}>
              Create Campaign
            </NavLink>
            <NavLink to="/customers" className={({ isActive }) => `side-link ${isActive ? "active" : ""}`}>
              Customers
            </NavLink>
          </nav>
        </div>

        <div className="side-footer">
          <div className="side-footer-label">Backend</div>
          <div className="side-footer-value">localhost:8000</div>
        </div>
      </aside>

      <main className="page-area">
        <Outlet />
      </main>
    </div>
  );
}

