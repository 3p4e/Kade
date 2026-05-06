import { useEffect, useState } from 'react'
import { api } from '../lib/api.js'
import { useAuth } from '../hooks/useAuth.jsx'

const TABS = [
  { key: 'proposed', label: 'Proposed (auto-discovered)' },
  { key: 'approved', label: 'Approved' },
  { key: 'deprecated', label: 'Deprecated' },
]

export default function Placeholders() {
  const { user } = useAuth()
  const [tab, setTab] = useState('proposed')
  const [rows, setRows] = useState([])
  const [err, setErr] = useState('')
  const [show, setShow] = useState(false)
  const [form, setForm] = useState({ key: '', label: '', data_type: 'string', description: '' })

  async function load() {
    try { setRows(await api.listPlaceholders(tab)) }
    catch (e) { setErr(e.message) }
  }
  useEffect(() => { load() }, [tab])

  async function decide(id, status) {
    await api.decidePlaceholder(id, status)
    await load()
  }

  async function createNew(e) {
    e.preventDefault()
    try {
      await api.createPlaceholder(form)
      setShow(false); setForm({ key: '', label: '', data_type: 'string', description: '' })
      await load()
    } catch (e) { alert(e.message) }
  }

  const canEdit = user?.role === 'admin' || user?.role === 'analyst'

  return (
    <div className="space-y-3">
      <div className="card p-3 flex items-center justify-between">
        <div className="flex gap-2">
          {TABS.map(t => (
            <button key={t.key} onClick={() => setTab(t.key)}
              className={`btn ${tab === t.key ? 'bg-indigo-600 text-white' : 'btn-secondary'}`}>
              {t.label}
            </button>
          ))}
        </div>
        {canEdit && <button className="btn-primary" onClick={() => setShow(true)}>+ Add placeholder</button>}
      </div>

      {err && <div className="text-red-600 text-sm">{err}</div>}

      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-slate-600 text-left">
            <tr>
              <th className="px-3 py-2">Key</th>
              <th className="px-3 py-2">Label</th>
              <th className="px-3 py-2">Type</th>
              <th className="px-3 py-2">Seen</th>
              <th className="px-3 py-2">Discovered</th>
              <th className="px-3 py-2"></th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {rows.length === 0 && (
              <tr><td colSpan={6} className="px-3 py-6 text-slate-500">Nothing here.</td></tr>
            )}
            {rows.map(p => (
              <tr key={p.id}>
                <td className="px-3 py-2 font-mono text-xs">{p.key}</td>
                <td className="px-3 py-2">{p.label}</td>
                <td className="px-3 py-2 text-slate-500">{p.data_type}</td>
                <td className="px-3 py-2">{p.occurrence_count}</td>
                <td className="px-3 py-2 text-slate-500">{new Date(p.discovered_at).toLocaleString()}</td>
                <td className="px-3 py-2 text-right">
                  {user?.role === 'admin' && tab === 'proposed' && (
                    <div className="flex gap-2 justify-end">
                      <button className="btn-secondary" onClick={() => decide(p.id, 'approved')}>Approve</button>
                      <button className="btn-danger" onClick={() => decide(p.id, 'deprecated')}>Deprecate</button>
                    </div>
                  )}
                  {user?.role === 'admin' && tab === 'approved' && (
                    <button className="btn-danger" onClick={() => decide(p.id, 'deprecated')}>Deprecate</button>
                  )}
                  {user?.role === 'admin' && tab === 'deprecated' && (
                    <button className="btn-secondary" onClick={() => decide(p.id, 'approved')}>Re-approve</button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {show && (
        <div className="fixed inset-0 bg-black/40 grid place-items-center z-50">
          <form onSubmit={createNew} className="card p-4 w-full max-w-md space-y-3">
            <h3 className="font-semibold">New placeholder field</h3>
            <div>
              <label className="label">Key</label>
              <input className="input" value={form.key}
                onChange={(e) => setForm({ ...form, key: e.target.value })}
                pattern="[a-z0-9_]+" required />
            </div>
            <div>
              <label className="label">Label</label>
              <input className="input" value={form.label}
                onChange={(e) => setForm({ ...form, label: e.target.value })} required />
            </div>
            <div>
              <label className="label">Type</label>
              <select className="input" value={form.data_type}
                onChange={(e) => setForm({ ...form, data_type: e.target.value })}>
                <option value="string">String</option>
                <option value="number">Number</option>
                <option value="date">Date</option>
                <option value="bool">Boolean</option>
                <option value="enum">Enum</option>
              </select>
            </div>
            <div>
              <label className="label">Description</label>
              <textarea className="input" rows={2} value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })} />
            </div>
            <div className="flex justify-end gap-2">
              <button type="button" className="btn-secondary" onClick={() => setShow(false)}>Cancel</button>
              <button type="submit" className="btn-primary">Create</button>
            </div>
          </form>
        </div>
      )}
    </div>
  )
}
