import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../lib/api.js'
import StatusTag from '../components/StatusTag.jsx'

function Stat({ label, value, accent }) {
  return (
    <div className="card p-4">
      <div className="text-xs text-slate-500">{label}</div>
      <div className={`text-2xl font-semibold ${accent || ''}`}>{value}</div>
    </div>
  )
}

export default function Dashboard() {
  const [data, setData] = useState(null)
  const [err, setErr] = useState('')

  useEffect(() => {
    api.dashboard().then(setData).catch((e) => setErr(e.message))
  }, [])

  if (err) return <div className="text-red-600 text-sm">{err}</div>
  if (!data) return <div className="text-slate-500">Loading…</div>

  const t = data.totals
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        <Stat label="Total CoAs" value={t.all} />
        <Stat label="Pass" value={t.pass} accent="text-emerald-600" />
        <Stat label="Fail" value={t.fail} accent="text-red-600" />
        <Stat label="Review" value={t.review} accent="text-amber-600" />
        <Stat label="Last 30 days" value={t.last_30_days} />
        <Stat label="Placeholders to review" value={t.placeholders_proposed} />
      </div>

      <div className="grid md:grid-cols-2 gap-4">
        <div className="card p-4">
          <h3 className="font-semibold mb-2">Recent CoAs</h3>
          <div className="divide-y">
            {data.recent_coas.length === 0 && <div className="text-sm text-slate-500">No CoAs yet.</div>}
            {data.recent_coas.map((c) => (
              <Link key={c.id} to={`/coas/${c.id}`} className="block py-2 hover:bg-slate-50 px-2 -mx-2 rounded">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-sm font-medium">{c.doc_code || '(no code)'} — batch {c.batch_number || '?'}</div>
                    <div className="text-xs text-slate-500">{c.product_name || ''}</div>
                  </div>
                  <StatusTag status={c.overall_status} />
                </div>
              </Link>
            ))}
          </div>
        </div>

        <div className="card p-4">
          <h3 className="font-semibold mb-2">Accreditations expiring within 60 days</h3>
          <div className="divide-y">
            {data.expiring_accreditations.length === 0 && <div className="text-sm text-slate-500">None.</div>}
            {data.expiring_accreditations.map((l) => (
              <div key={l.id} className="py-2 text-sm flex justify-between">
                <span>{l.name}</span>
                <span className="text-amber-700">{l.valid_until}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
