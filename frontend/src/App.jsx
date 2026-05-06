import { Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider, useAuth } from './hooks/useAuth.jsx'
import Layout from './components/Layout.jsx'
import Login from './pages/Login.jsx'
import Dashboard from './pages/Dashboard.jsx'
import CoaList from './pages/CoaList.jsx'
import CoaDetail from './pages/CoaDetail.jsx'
import Upload from './pages/Upload.jsx'
import Ask from './pages/Ask.jsx'
import Placeholders from './pages/Placeholders.jsx'
import Labs from './pages/Labs.jsx'
import Audit from './pages/Audit.jsx'

function Gate({ children }) {
  const { user, loading } = useAuth()
  if (loading) return <div className="p-6 text-slate-500">Loading…</div>
  if (!user) return <Navigate to="/login" replace />
  return children
}

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route element={<Gate><Layout /></Gate>}>
          <Route index element={<Dashboard />} />
          <Route path="coas" element={<CoaList />} />
          <Route path="coas/:id" element={<CoaDetail />} />
          <Route path="upload" element={<Upload />} />
          <Route path="ask" element={<Ask />} />
          <Route path="placeholders" element={<Placeholders />} />
          <Route path="labs" element={<Labs />} />
          <Route path="audit" element={<Audit />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AuthProvider>
  )
}
