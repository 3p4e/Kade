import { useEffect, useState } from 'react'
import { api } from '../lib/api.js'

export default function Audit() {
  const [rows, setRows] = useState([])
  const [err, setErr] = useState('')

  useEffect(() => {
    api.audit({ limit: 200 }).then(setRows).catch(e => setErr(e.message))
  }, [])

  if (err) return <div className="text-red-600 text-sm">{err}</div>

  return (
    <div className="card overflow-hidden">
      <table className="w-full text-sm">
        <thead className="bg-slate-50 text-left text-slate-600">
          <tr>
            <th className="px-3 py-2">When</th>
            <th className="px-3 py-2">Actor</th>
            <th className="px-3 py-2">Action</th>
            <th className="px-3 py-2">Entity</th>
            <th className="px-3 py-2">ID</th>
          </tr>
        </thead>
        <tbody className="divide-y">
          {rows.length === 0 && <tr><td colSpan={5} className="px-3 py-6 text-slate-500">No audit entries.</td></tr>}
          {rows.map(r => (
            <tr key={r.id} className="align-top">
              <td className="px-3 py-2 whitespace-nowrap text-slate-500">{new Date(r.occurred_at).toLocaleString()}</td>
              <td className="px-3 py-2">{r.actor_email || '—'}</td>
              <td className="px-3 py-2 font-medium">{r.action}</td>
              <td className="px-3 py-2">{r.entity}</td>
              <td className="px-3 py-2 font-mono text-xs">{r.entity_id || '—'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
