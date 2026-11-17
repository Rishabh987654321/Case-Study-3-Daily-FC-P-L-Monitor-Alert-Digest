import { Link, NavLink, Outlet } from "react-router-dom";

export function Layout() {
  return (
    <div className="min-h-screen bg-gray-50">
      <header className="border-b border-gray-200 bg-white">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-3">
          <Link to="/upload" className="text-lg font-bold text-gray-900">
            FC P&amp;L Monitor
          </Link>
          <nav className="flex gap-6 text-sm font-medium">
            <NavLink
              to="/upload"
              className={({ isActive }) =>
                isActive ? "text-indigo-600" : "text-gray-600 hover:text-gray-900"
              }
            >
              Upload
            </NavLink>
            <NavLink
              to="/history"
              className={({ isActive }) =>
                isActive ? "text-indigo-600" : "text-gray-600 hover:text-gray-900"
              }
            >
              History
            </NavLink>
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-6 py-6">
        <Outlet />
      </main>
    </div>
  );
}
