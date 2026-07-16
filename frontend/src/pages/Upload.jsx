import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../lib/api.js'

export default function Upload() {
  const nav = useNavigate()
  const [files, setFiles] = useState([])
  const [method, setMethod] = useState('upload')
  const [progress, setProgress] = useState([])
  const [working, setWorking] = useState(false)

  function onPick(e) {
    setFiles(Array.from(e.target.files || []))
    setProgress([])
  }

  async function go() {
    setWorking(true)
    const out = []
    for (const f of files) {
      out.push({ name: f.name, status: 'uploading…' })
      setProgress([...out])
      try {
        const coa = await api.uploadCoa(f, method)
        out[out.length - 1] = { name: f.name, status: 'done', coaId: coa.id, doc: coa.doc_code, batch: coa.batch_number }
      } catch (e) {
        out[out.length - 1] = { name: f.name, status: 'error: ' + (e.message || 'failed') }
      }
      setProgress([...out])
    }
    setWorking(false)
  }

  return (
    <div className="space-y-3 max-w-2xl">
      <div className="card p-4">
        <h2 className="font-semibold">Upload CoA PDFs</h2>
        <p className="text-sm text-slate-500">
          PDFs are OCR-processed if needed, fields are auto-extracted, and the document is
          chunked + embedded for RAG search. Discovered new fields appear in the
          Placeholders queue for review.
        </p>
        <div className="mt-3 flex gap-3 items-end">
          <div>
            <label className="label">Source</label>
            <select className="input" value={method} onChange={(e) => setMethod(e.target.value)}>
              <option value="upload">Upload (electronic)</option>
              <option value="scan">Scan (OCR)</option>
            </select>
          </div>
          <input className="input" type="file" multiple accept="application/pdf" onChange={onPick} />
          <button className="btn-primary" onClick={go} disabled={!files.length || working}>
            {working ? 'Working…' : `Ingest ${files.length || ''}`}
          </button>
        </div>
      </div>

      {progress.length > 0 && (
        <div className="card p-4">
          <h3 className="font-semibold mb-2">Results</h3>
          <ul className="text-sm divide-y">
            {progress.map((p, i) => (
              <li key={i} className="py-2 flex items-center justify-between gap-2">
                <span className="truncate">{p.name}</span>
                {p.coaId ? (
                  <button className="text-indigo-600 hover:underline text-sm"
                    onClick={() => nav(`/coas/${p.coaId}`)}>
                    {p.doc || '(no code)'} / {p.batch || '—'} ↗
                  </button>
                ) : (
                  <span className={p.status.startsWith('error') ? 'text-red-600' : 'text-slate-500'}>{p.status}</span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
