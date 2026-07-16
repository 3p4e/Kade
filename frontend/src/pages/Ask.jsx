import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../lib/api.js'

export default function Ask() {
  const [q, setQ] = useState('Which CoAs failed microbial limits in the last quarter?')
  const [topK, setTopK] = useState(6)
  const [loading, setLoading] = useState(false)
  const [resp, setResp] = useState(null)
  const [err, setErr] = useState('')

  async function ask(e) {
    e?.preventDefault()
    setErr(''); setResp(null); setLoading(true)
    try {
      const r = await api.ask(q, { top_k: topK })
      setResp(r)
    } catch (e) {
      setErr(e.message)
    } finally { setLoading(false) }
  }

  return (
    <div className="space-y-3">
      <form onSubmit={ask} className="card p-4 space-y-3">
        <div>
          <label className="label">Ask the CoA knowledge base</label>
          <textarea className="input" rows={3} value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
        <div className="flex items-end gap-3">
          <div>
            <label className="label">Top K</label>
            <input className="input w-24" type="number" min={1} max={20} value={topK} onChange={(e) => setTopK(parseInt(e.target.value || '6', 10))} />
          </div>
          <button className="btn-primary" disabled={loading || !q.trim()}>{loading ? 'Asking…' : 'Ask'}</button>
        </div>
      </form>

      {err && <div className="text-red-600 text-sm">{err}</div>}

      {resp && (
        <div className="card p-4 space-y-3">
          <div>
            <div className="text-xs text-slate-500">Answer</div>
            <div className="whitespace-pre-wrap text-sm">{resp.answer}</div>
          </div>
          <div>
            <div className="text-xs text-slate-500 mb-1">Citations</div>
            <ol className="space-y-2">
              {resp.citations.map((c, i) => (
                <li key={c.chunk_id} className="text-sm border rounded p-2">
                  <div className="flex justify-between">
                    <Link className="text-indigo-600 hover:underline" to={`/coas/${c.coa_id}`}>
                      [{i+1}] {c.doc_code || '(no code)'} · batch {c.batch_number || '?'} · p{c.page || '?'}
                    </Link>
                    <span className="text-slate-500">score {c.score.toFixed(2)}</span>
                  </div>
                  <div className="text-slate-700 mt-1">{c.snippet}</div>
                </li>
              ))}
            </ol>
          </div>
        </div>
      )}
    </div>
  )
}
