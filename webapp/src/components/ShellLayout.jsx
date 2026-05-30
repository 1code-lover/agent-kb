import { Link, Outlet, useLocation } from "react-router-dom";

const navs = [
  { to: "/agent", label: "Agent" },
  { to: "/models", label: "模型" },
  { to: "/knowledge", label: "知识库" }
];

export default function ShellLayout() {
  const location = useLocation();

  return (
    <div className="app-shell app-shell-minimal">
      <aside className="sidebar sidebar-minimal">
        <div className="sidebar-header sidebar-brand-block">
          <img className="sidebar-brand-mark" src="/northagent-mark.svg" alt="NorthAgent" />
          <span className="sidebar-title">NorthAgent</span>
          <span className="sidebar-subtitle">Desktop Agent Workspace</span>
        </div>

        <nav className="sidebar-nav sidebar-nav-minimal">
          {navs.map((item) => (
            <Link
              key={item.to}
              className={location.pathname === item.to || (location.pathname === "/" && item.to === "/agent") ? "active" : ""}
              to={item.to}
            >
              {item.label}
            </Link>
          ))}
        </nav>
      </aside>

      <main className="content content-minimal">
        <Outlet />
      </main>
    </div>
  );
}
