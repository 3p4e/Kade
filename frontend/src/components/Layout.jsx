import { NavLink, Outlet } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth.jsx'

const link = ({ isActive }) =>
  `block px-3 py-2 rounded-md text-sm font-medium ${
    isActive ? 'bg-indigo-600 text-white' : 'text-slate-700 hover:bg-slate-200'
  }`

export default function Layout() {
  const { user, logout } = useAuth()
  return (
    <div className="min-h-screen flex flex-col">
      <header className="bg-white border-b border-slate-200">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-md bg-indigo-600 text-white grid place-items-center font-bold">C</div>
            <h1 className="text-lg font-semibold">CoA Tracker</h1>
          </div>
          {user && (
            <div className="flex items-center gap-3">
              <span className="text-sm text-slate-600">{user.email} ({user.role})</span>
              <button className="btn-secondary" onClick={logout}>Sign out</button>
            </div>
          )}
        </div>
      </header>

      <div className="flex flex-1 max-w-7xl w-full mx-auto px-4 gap-4 py-4">
        <nav className="w-56 shrink-0 space-y-1">
          <NavLink to="/" end className={link}>Dashboard</NavLink>
          <NavLink to="/coas" className={link}>CoAs</NavLink>
          <NavLink to="/upload" className={link}>Upload</NavLink>
          <NavLink to="/ask" className={link}>RAG Ask</NavLink>
          <NavLink to="/placeholders" className={link}>Placeholders</NavLink>
          <NavLink to="/labs" className={link}>Laboratories</NavLink>
          {user?.role === 'admin' && <NavLink to="/audit" className={link}>Audit log</NavLink>}
        </nav>
        <main className="flex-1 min-w-0">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
