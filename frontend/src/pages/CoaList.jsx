import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api } from '../lib/api.js'
import StatusTag from '../components/StatusTag.jsx'

export default function CoaList() {
  const [params, setParams] = useSearchParams()
  const q = params.get('q') || ''
  const status = params.get('status') || ''
  const [data, setData] = useState({ items: [], total: 0 })
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState('')
  const limit = 50
  const offset = parseInt(params.get('offset') || '0', 10)

  useEffect(() => {
    setLoading(true)
    api.listCoas({ q, status, limit, offset })
      .then(setData)
      .catch((e) => setErr(e.message))
      .finally(() => setLoading(false))
  }, [q, status, offset])

  function setParam(k, v) {
    const next = new URLSearchParams(params)
    if (v) next.set(k, v); else next.delete(k)
    next.delete('offset')
    setParams(next)
  }

  return (
    <div className="space-y-3">
      <div className="card p-3 flex flex-wrap gap-3 items-end">
        <div className="flex-1 min-w-[200px]">
          <label className="label">Search</label>
          <input
            className="input"
            placeholder="Doc code, batch, product, strain…"
            defaultValue={q}
            onKeyDown={(e) => e.key === 'Enter' && setParam('q', e.currentTarget.value)}
          />
        </div>
        <div>
          <label className="label">Status</label>
          <select className="input" value={status} onChange={(e) => setParam('status', e.target.value)}>
            <option value="">All</option>
            <option value="PASS">PASS</option>
            <option value="FAIL">FAIL</option>
            <option value="REVIEW">REVIEW</option>
            <option value="PENDING">PENDING</option>
          </select>
        </div>
        <Link to="/upload" className="btn-primary">Upload PDF</Link>
      </div>

      {err && <div className="text-red-600 text-sm">{err}</div>}

      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-slate-600 text-left">
            <tr>
              <th className="px-3 py-2">Doc code</th>
              <th className="px-3 py-2">Batch</th>
              <th className="px-3 py-2">Product</th>
              <th className="px-3 py-2">Strain</th>
              <th className="px-3 py-2">Completed</th>
              <th className="px-3 py-2">Method</th>
              <th className="px-3 py-2">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {loading && (
              <tr><td colSpan={7} className="px-3 py-6 text-slate-500">Loading…</td></tr>
            )}
            {!loading && data.items.length === 0 && (
              <tr><td colSpan={7} className="px-3 py-6 text-slate-500">No CoAs match.</td></tr>
            )}
            {data.items.map((c) => (
              <tr key={c.id} className="hover:bg-slate-50">
                <td className="px-3 py-2"><Link className="text-indigo-600 hover:underline" to={`/coas/${c.id}`}>{c.doc_code || c.id.slice(0,8)}</Link></td>
                <td className="px-3 py-2">{c.batch_number || '—'}</td>
                <td className="px-3 py-2">{c.product_name || '—'}</td>
                <td className="px-3 py-2">{c.strain_name || '—'}</td>
                <td className="px-3 py-2">{c.analysis_completion_date || '—'}</td>
                <td className="px-3 py-2 text-slate-500">{c.ingestion_method}</td>
                <td className="px-3 py-2"><StatusTag status={c.overall_status} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="flex justify-between text-sm text-slate-600">
        <div>Total: {data.total}</div>
        <div className="flex gap-2">
          <button className="btn-secondary" disabled={offset === 0}
            onClick={() => setParam('offset', Math.max(0, offset - limit) || '')}>Prev</button>
          <button className="btn-secondary" disabled={offset + limit >= data.total}
            onClick={() => setParam('offset', String(offset + limit))}>Next</button>
        </div>
      </div>
    </div>
  )
}
