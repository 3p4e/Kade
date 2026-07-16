import { useEffect, useState } from 'react'
import { api } from '../lib/api.js'
import { useAuth } from '../hooks/useAuth.jsx'

const empty = {
  name: '', location: '', address: '', accreditation_body: '', accreditation_number: '',
  accreditation_standard: 'ISO/IEC 17025:2017', accreditation_valid_until: '',
  contact_email: '', contact_phone: '', notes: '',
}

export default function Labs() {
  const { user } = useAuth()
  const [rows, setRows] = useState([])
  const [err, setErr] = useState('')
  const [show, setShow] = useState(false)
  const [form, setForm] = useState(empty)

  async function load() {
    try { setRows(await api.listLabs()) } catch (e) { setErr(e.message) }
  }
  useEffect(() => { load() }, [])

  async function submit(e) {
    e.preventDefault()
    try {
      const payload = { ...form }
      if (!payload.accreditation_valid_until) delete payload.accreditation_valid_until
      await api.createLab(payload)
      setShow(false); setForm(empty); load()
    } catch (e) { alert(e.message) }
  }

  return (
    <div className="space-y-3">
      <div className="flex justify-between">
        <h2 className="text-lg font-semibold">Laboratories</h2>
        {(user?.role === 'admin' || user?.role === 'analyst') && (
          <button className="btn-primary" onClick={() => setShow(true)}>+ Add lab</button>
        )}
      </div>
      {err && <div className="text-red-600 text-sm">{err}</div>}
      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-slate-600">
            <tr>
              <th className="px-3 py-2">Name</th>
              <th className="px-3 py-2">Location</th>
              <th className="px-3 py-2">Accreditation</th>
              <th className="px-3 py-2">Valid until</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {rows.length === 0 && <tr><td colSpan={4} className="px-3 py-6 text-slate-500">No laboratories yet.</td></tr>}
            {rows.map(l => (
              <tr key={l.id}>
                <td className="px-3 py-2 font-medium">{l.name}</td>
                <td className="px-3 py-2 text-slate-600">{l.location || '—'}</td>
                <td className="px-3 py-2 text-slate-600">{[l.accreditation_standard, l.accreditation_number].filter(Boolean).join(' · ')}</td>
                <td className="px-3 py-2">{l.accreditation_valid_until || '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {show && (
        <div className="fixed inset-0 bg-black/40 grid place-items-center z-50">
          <form onSubmit={submit} className="card p-4 w-full max-w-lg space-y-2">
            <h3 className="font-semibold">New laboratory</h3>
            {Object.keys(empty).map(k => (
              <div key={k}>
                <label className="label">{k.replace(/_/g,' ')}</label>
                {k === 'address' || k === 'notes' ? (
                  <textarea className="input" rows={2} value={form[k]}
                    onChange={(e) => setForm({ ...form, [k]: e.target.value })} />
                ) : (
                  <input className="input" type={k.endsWith('_until') ? 'date' : 'text'}
                    required={k === 'name'} value={form[k]}
                    onChange={(e) => setForm({ ...form, [k]: e.target.value })} />
                )}
              </div>
            ))}
            <div className="flex justify-end gap-2 pt-2">
              <button type="button" className="btn-secondary" onClick={() => setShow(false)}>Cancel</button>
              <button type="submit" className="btn-primary">Save</button>
            </div>
          </form>
        </div>
      )}
    </div>
  )
}
