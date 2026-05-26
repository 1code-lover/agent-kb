/**
 * 文件功能：
 * - 提供桌面端页面通用壳层布局（侧边导航 + 内容区）。
 */

import { Link, Outlet, useLocation } from "react-router-dom";

const navs = [
  { to: "/", label: "Workspace" },
  { to: "/kb-file", label: "KB File" },
  { to: "/settings", label: "Settings" },
  { to: "/models", label: "Models" },
  { to: "/kb-manage", label: "KB Manage" },
  { to: "/kb-web", label: "KB Web" },
  { to: "/storage", label: "Storage" },
  { to: "/advanced", label: "Advanced" }
];

/**
 * 功能：
 * - 渲染应用主壳层并标记当前激活导航。
 *
 * 输出：
 * - JSX.Element: 应用壳层布局。
 */
export default function ShellLayout() {
  const location = useLocation();
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <h1>ThinkRAG</h1>
        {navs.map((item) => (
          <Link key={item.to} className={location.pathname === item.to ? "active" : ""} to={item.to}>
            {item.label}
          </Link>
        ))}
      </aside>
      <main className="content">
        <Outlet />
      </main>
    </div>
  );
}
