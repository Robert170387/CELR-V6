import React from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from '@/context/AuthContext'
import Login from '@/pages/Login'
import Dashboard from '@/pages/Dashboard'
import Viajes from '@/pages/Viajes'
import Gastos from '@/pages/Gastos'
import ScanReceipt from '@/pages/ScanReceipt'
import Liquidaciones from '@/pages/Liquidaciones'
import Maestras from '@/pages/Maestras'
import Layout from '@/components/Layout'
import { puedeAccederModulo } from '@/utils/rbac'

const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isAuthenticated } = useAuth()
  if (!isAuthenticated) return <Navigate to="/login" replace />
  return <>{children}</>
}

const RequireRole: React.FC<{ path: string; children: React.ReactNode }> = ({ path, children }) => {
  const { user } = useAuth()
  if (user && !puedeAccederModulo(path, user.rol)) return <Navigate to="/" replace />
  return <>{children}</>
}

const AppRoutes: React.FC = () => {
  const { isAuthenticated } = useAuth()

  return (
    <Routes>
      <Route path="/login" element={isAuthenticated ? <Navigate to="/" replace /> : <Login />} />
      <Route
        path="/*"
        element={
          <ProtectedRoute>
            <Layout>
              <Routes>
                <Route path="/" element={<Dashboard />} />
                <Route path="/viajes" element={<Viajes />} />
                <Route path="/gastos" element={<Gastos />} />
                <Route
                  path="/scan"
                  element={
                    <RequireRole path="/scan">
                      <ScanReceipt />
                    </RequireRole>
                  }
                />
                <Route
                  path="/liquidaciones"
                  element={
                    <RequireRole path="/liquidaciones">
                      <Liquidaciones />
                    </RequireRole>
                  }
                />
                <Route
                  path="/maestras"
                  element={
                    <RequireRole path="/maestras">
                      <Maestras />
                    </RequireRole>
                  }
                />
                <Route path="*" element={<Navigate to="/" replace />} />
              </Routes>
            </Layout>
          </ProtectedRoute>
        }
      />
    </Routes>
  )
}

const App: React.FC = () => (
  <BrowserRouter>
    <AuthProvider>
      <AppRoutes />
    </AuthProvider>
  </BrowserRouter>
)

export default App
