import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { api } from '../lib/api.js'
import StatusTag from '../components/StatusTag.jsx'

function Field({ label, value }) {
  return (
    <div>
      <div className="text-xs text-slate-500">{label}</div>
      <div className="text-sm">{value ?? '—'}</div>
    </div>
  )
}

export default function CoaDetail() {
  const { id } = useParams()
  const [coa, setCoa] = useState(null)
  const [err, setErr] = useState('')
  const [askQ, setAskQ] = useState('Summarize this CoA.')
  const [answer, setAnswer] = useState(null)
  const [asking, setAsking] = useState(false)

  useEffect(() => { api.getCoa(id).then(setCoa).catch((e) => setErr(e.message)) }, [id])

  async function ask() {
    setAsking(true); setAnswer(null)
    try {
      const a = await api.ask(askQ, { coa_ids: [id], top_k: 8 })
      setAnswer(a)
    } catch (e) {
      setAnswer({ answer: 'Error: ' + e.message, citations: [] })
    } finally { setAsking(false) }
  }

  if (err) return <div className="text-red-600 text-sm">{err}</div>
  if (!coa) return <div className="text-slate-500">Loading…</div>

  return (
    <div className="grid lg:grid-cols-3 gap-4">
      <div className="lg:col-span-2 space-y-4">
        <div className="card p-4">
          <div className="flex justify-between items-start">
            <div>
              <h2 className="text-lg font-semibold">{coa.doc_code || '(no doc code)'}</h2>
              <div className="text-sm text-slate-500">Batch {coa.batch_number || '?'} · {coa.product_name || '—'}</div>
            </div>
            <StatusTag status={coa.overall_status} />
          </div>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3 mt-4">
            <Field label="Sample ID" value={coa.sample_id} />
            <Field label="Strain" value={coa.strain_name} />
            <Field label="Potency" value={coa.potency} />
            <Field label="Manufacturer" value={coa.manufacturer_name} />
            <Field label="Sample receipt" value={coa.sample_receipt_date} />
            <Field label="Analysis start" value={coa.analysis_start_date} />
            <Field label="Analysis completed" value={coa.analysis_completion_date} />
            <Field label="Ingested" value={new Date(coa.ingested_at).toLocaleString()} />
            <Field label="Method" value={coa.ingestion_method} />
          </div>
        </div>

        <div className="card p-4">
          <h3 className="font-semibold mb-3">Parameters</h3>
          {coa.parameters?.length ? (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="text-left text-slate-500">
                  <tr>
                    <th className="py-1 pr-3">Parameter</th>
                    <th className="py-1 pr-3">Method</th>
                    <th className="py-1 pr-3">Result</th>
                    <th className="py-1 pr-3">Spec</th>
                    <th className="py-1 pr-3">P/F</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {coa.parameters.map((p) => (
                    <tr key={p.id}>
                      <td className="py-1 pr-3 font-medium">{p.name}</td>
                      <td className="py-1 pr-3 text-slate-500">{p.method || '—'}</td>
                      <td className="py-1 pr-3">{p.result || '—'}</td>
                      <td className="py-1 pr-3">{p.specification || '—'}</td>
                      <td className="py-1 pr-3"><StatusTag status={p.pass_fail} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="text-sm text-slate-500">No parameters extracted.</div>
          )}
        </div>

        {Object.keys(coa.extra_fields || {}).length > 0 && (
          <div className="card p-4">
            <h3 className="font-semibold mb-3">Discovered fields (placeholders)</h3>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
              {Object.entries(coa.extra_fields).map(([k, v]) => (
                <Field key={k} label={k} value={typeof v === 'object' ? JSON.stringify(v) : String(v)} />
              ))}
            </div>
          </div>
        )}
      </div>

      <div className="space-y-4">
        <div className="card p-3">
          <h3 className="font-semibold mb-2">Source PDF</h3>
          {coa.file_path ? (
            <iframe
              title="pdf"
              src={api.pdfUrl(coa.id) + `?token=${encodeURIComponent(api.getToken())}`}
              className="w-full h-[500px] border"
            />
          ) : (
            <div className="text-sm text-slate-500">No PDF on file.</div>
          )}
          <a className="btn-secondary mt-2 inline-block" href={api.pdfUrl(coa.id)} target="_blank" rel="noreferrer">Open in new tab</a>
        </div>

        <div className="card p-3">
          <h3 className="font-semibold mb-2">Ask about this CoA</h3>
          <textarea className="input" rows={3} value={askQ} onChange={(e) => setAskQ(e.target.value)} />
          <button className="btn-primary mt-2" onClick={ask} disabled={asking}>
            {asking ? 'Asking…' : 'Ask'}
          </button>
          {answer && (
            <div className="mt-3 text-sm whitespace-pre-wrap">
              <div className="font-medium mb-1">Answer</div>
              <div>{answer.answer}</div>
              {answer.citations?.length > 0 && (
                <div className="mt-2 text-xs text-slate-500">
                  <div className="font-medium">Citations</div>
                  <ol className="list-decimal pl-5">
                    {answer.citations.map((c, i) => (
                      <li key={c.chunk_id}>p{c.page || '?'} · score {c.score.toFixed(2)} — {c.snippet}</li>
                    ))}
                  </ol>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
