const BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'

function getToken() {
  return localStorage.getItem('coa_token') || ''
}

async function req(path, { method = 'GET', body, headers = {}, isForm = false } = {}) {
  const token = getToken()
  const h = { ...headers }
  if (token) h.Authorization = `Bearer ${token}`
  if (!isForm && body !== undefined) h['Content-Type'] = 'application/json'
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers: h,
    body: isForm ? body : body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) {
    let detail
    try { detail = await res.json() } catch { detail = { detail: await res.text() } }
    const err = new Error(detail.detail || res.statusText)
    err.status = res.status
    err.detail = detail
    throw err
  }
  if (res.status === 204) return null
  const ct = res.headers.get('content-type') || ''
  return ct.includes('application/json') ? res.json() : res.blob()
}

export const api = {
  base: BASE,
  setToken(t) { if (t) localStorage.setItem('coa_token', t); else localStorage.removeItem('coa_token') },
  getToken,
  login: (email, password) => req('/auth/login', { method: 'POST', body: { email, password } }),
  me: () => req('/auth/me'),

  listCoas: (params = {}) => {
    const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v !== undefined && v !== '' && v !== null))
    return req(`/coas?${qs.toString()}`)
  },
  getCoa: (id) => req(`/coas/${id}`),
  updateCoa: (id, payload) => req(`/coas/${id}`, { method: 'PATCH', body: payload }),
  deleteCoa: (id) => req(`/coas/${id}`, { method: 'DELETE' }),
  uploadCoa: (file, ingestion_method = 'upload') => {
    const fd = new FormData()
    fd.append('file', file)
    fd.append('ingestion_method', ingestion_method)
    return req('/coas/upload', { method: 'POST', body: fd, isForm: true })
  },
  pdfUrl: (id) => `${BASE}/coas/${id}/file`,

  listLabs: () => req('/laboratories'),
  createLab: (payload) => req('/laboratories', { method: 'POST', body: payload }),

  listPlaceholders: (status) => req(`/placeholders${status ? `?status=${status}` : ''}`),
  decidePlaceholder: (id, status) => req(`/placeholders/${id}/decision`, { method: 'POST', body: { status } }),
  createPlaceholder: (payload) => req('/placeholders', { method: 'POST', body: payload }),

  ask: (question, opts = {}) => req('/rag/ask', { method: 'POST', body: { question, top_k: opts.top_k || 6, coa_ids: opts.coa_ids } }),

  dashboard: () => req('/dashboard/summary'),
  audit: (params = {}) => {
    const qs = new URLSearchParams(Object.entries(params).filter(([, v]) => v !== undefined && v !== ''))
    return req(`/audit?${qs.toString()}`)
  },
}
