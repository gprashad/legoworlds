import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { ProtectedRoute } from './components/layout/ProtectedRoute'
import { LoginPage } from './pages/LoginPage'
import { ScenesPage } from './pages/ScenesPage'
import { SceneWorkspace } from './pages/SceneWorkspace'
import { ScreenplayReview } from './pages/ScreenplayReview'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route
          path="/scenes"
          element={
            <ProtectedRoute>
              <ScenesPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/scenes/:id"
          element={
            <ProtectedRoute>
              <SceneWorkspace />
            </ProtectedRoute>
          }
        />
        <Route
          path="/scenes/:id/screenplay"
          element={
            <ProtectedRoute>
              <ScreenplayReview />
            </ProtectedRoute>
          }
        />
        <Route path="*" element={<Navigate to="/scenes" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
