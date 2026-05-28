import { Link, Outlet, useLocation } from "react-router-dom";

const navs = [
  { to: "/", label: "Agent" },
  { to: "/kb-file", label: "Import Files" },
  { to: "/kb-web", label: "Import Web" },
  { to: "/kb-manage", label: "KB Manage" },
  { to: "/models", label: "Models" },
  { to: "/settings", label: "Settings" },
  { to: "/storage", label: "Storage" },
  { to: "/advanced", label: "Advanced" }
];

export default function ShellLayout() {
  const location = useLocation();

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand-block">
          <p className="brand-eyebrow">Desktop Only</p>
          <h1>Foxglove</h1>
          <p className="brand-copy">Agent first. KB as tool.</p>
        </div>
        <nav className="sidebar-nav">
          {navs.map((item) => (
            <Link key={item.to} className={location.pathname === item.to ? "active" : ""} to={item.to}>
              {item.label}
            </Link>
          ))}
        </nav>
      </aside>
      <main className="content">
        <Outlet />
      </main>
    </div>
  );
}
